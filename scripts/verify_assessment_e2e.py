"""Run the real HTTP assessment lifecycle and remove only data created by this run.

The backend must already be listening. Database configuration is loaded from the
same environment as the application; this script never substitutes SQLite.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


def request_json(base_url: str, method: str, path: str, body=None, token: str | None = None):
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(f"{base_url}{path}", data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=60) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} -> HTTP {exc.code}: {detail}") from exc
    if isinstance(decoded, dict) and "code" in decoded:
        if decoded.get("code") != 0:
            raise RuntimeError(f"{method} {path} -> {decoded.get('code')}: {decoded.get('message')}")
        return decoded.get("data")
    return decoded


def cleanup(engine, ids: dict, original_talent_level) -> None:
    result_id = ids.get("result")
    with engine.begin() as connection:
        if result_id:
            connection.execute(text(
                "DELETE FROM msg_center WHERE biz_id=:result_id "
                "AND biz_type IN ('assessment_result', 'assessment_training')"
            ), {"result_id": result_id})
        if ids.get("plan"):
            connection.execute(text("DELETE FROM trn_training_plan WHERE id=:id"), {"id": ids["plan"]})
        if result_id:
            connection.execute(text("DELETE FROM asm_training_outbox WHERE result_id=:id"), {"id": result_id})
            connection.execute(text("DELETE FROM asm_answer_event WHERE result_id=:id"), {"id": result_id})
            connection.execute(text("DELETE FROM asm_result_detail WHERE result_id=:id"), {"id": result_id})
            connection.execute(text("DELETE FROM ai_agent_task WHERE result_id=:id"), {"id": result_id})
            connection.execute(text("DELETE FROM asm_result WHERE id=:id"), {"id": result_id})
        if ids.get("batch"):
            connection.execute(text("DELETE FROM asm_assessment_batch WHERE id=:id"), {"id": ids["batch"]})
        if ids.get("paper"):
            connection.execute(text("DELETE FROM asm_paper_question WHERE paper_id=:id"), {"id": ids["paper"]})
            connection.execute(text("DELETE FROM asm_paper WHERE id=:id"), {"id": ids["paper"]})
        if ids.get("question"):
            connection.execute(text("DELETE FROM asm_question WHERE id=:id"), {"id": ids["question"]})
        if ids.get("bank"):
            connection.execute(text("DELETE FROM asm_question_bank WHERE id=:id"), {"id": ids["bank"]})
        if ids.get("talent"):
            connection.execute(text(
                "UPDATE tal_talent SET level=:level WHERE id=:id"
            ), {"level": original_talent_level, "id": ids["talent"]})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--keep-data", action="store_true")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
    ids: dict[str, int] = {}
    original_talent_level = None
    marker = f"E2E-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}"
    stages: list[str] = []

    try:
        health = request_json(base_url, "GET", "/health")
        assert health.get("status") == "ok"
        stages.append("后端健康检查")

        admin_login = request_json(base_url, "POST", "/api/v1/auth/login", {
            "username": "admin", "password": "admin123",
        })
        employee_login = request_json(base_url, "POST", "/api/v1/auth/employee-login", {
            "username": "assessment_demo", "password": "assessment123",
        })
        admin_token = admin_login["access_token"]
        employee_token = employee_login["access_token"]
        talent_id = int(employee_login["user"]["talent_id"])
        ids["talent"] = talent_id
        with engine.connect() as connection:
            original_talent_level = connection.execute(text(
                "SELECT level FROM tal_talent WHERE id=:id"
            ), {"id": talent_id}).scalar()
        stages.append("管理端/员工端登录")

        bank = request_json(base_url, "POST", "/api/v1/assessment/banks", {
            "name": f"{marker}-题库", "description": "自动验收，结束后删除",
        }, admin_token)
        ids["bank"] = int(bank["id"])
        question = request_json(base_url, "POST", "/api/v1/assessment/questions", {
            "bank_id": ids["bank"], "type": "single", "content": f"{marker} 验收题",
            "options": ["A", "B"], "answer": ["A"], "dimension": "E2E质量", "difficulty": 1,
            "score": 10,
        }, admin_token)
        ids["question"] = int(question["id"])
        listed = request_json(base_url, "GET", f"/api/v1/assessment/banks/{ids['bank']}/questions", token=admin_token)
        assert [item["id"] for item in listed] == [ids["question"]]
        stages.append("题库与题目")

        paper = request_json(base_url, "POST", "/api/v1/assessment/papers", {
            "title": f"{marker}-试卷", "description": "自动验收",
            "duration": 30, "question_ids": [ids["question"]],
        }, admin_token)
        ids["paper"] = int(paper["id"])
        paper_detail = request_json(base_url, "GET", f"/api/v1/assessment/papers/{ids['paper']}", token=admin_token)
        assert len(paper_detail["questions"]) == 1 and paper_detail["questions"][0]["question_id"] == ids["question"]
        stages.append("手动组卷")

        launch = request_json(base_url, "POST", "/api/v1/assessment/launch", {
            "paper_id": ids["paper"], "talent_ids": [talent_id], "batch_name": f"{marker}-批次",
        }, admin_token)
        assert len(launch) == 1 and int(launch[0]["talent_id"]) == talent_id
        ids["result"] = int(launch[0]["result_id"])
        ids["batch"] = int(launch[0]["batch_id"])
        stages.append("按人才档案发起")

        snapshot = request_json(base_url, "GET", f"/api/v1/assessment/result/{ids['result']}/answer", token=employee_token)
        # Opening the answer page may transition the response snapshot from
        # not-started (0) to in-progress (1), depending on service policy.
        assert snapshot["status"] in {0, 1}
        assert snapshot["questions"][0]["question_id"] == ids["question"]
        answers = {str(ids["question"]): "A"}
        saved = request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/answer", {"answers": answers}, employee_token)
        assert saved["status"] == 1 and saved["answers"] == answers
        request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/events", {
            "event_type": "focus", "detail": "e2e", "source": "acceptance",
        }, employee_token)
        stages.append("在线作答与暂存")

        submitted = request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/submit", {"answers": answers}, employee_token)
        assert submitted["result"]["status"] == 2
        assert float(submitted["result"]["score"]) == 10 and submitted["result"]["correct_count"] == 1
        my_result = request_json(base_url, "GET", f"/api/v1/assessment/my-result/{ids['result']}", token=employee_token)
        assert my_result["details"][0]["is_correct"] == 1
        stages.append("交卷、判分与个人成绩")

        detail = request_json(base_url, "GET", f"/api/v1/assessment/result/{ids['result']}", token=admin_token)
        statistics = request_json(base_url, "GET", f"/api/v1/assessment/results/statistics?batch_id={ids['batch']}", token=admin_token)
        assert detail["result"]["status"] == 2 and statistics["completed_results"] == 1
        stages.append("管理端明细与统计")

        report = request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/report", {}, admin_token)
        assert report["result_id"] == ids["result"] and report["source"] == "local"
        fetched_report = request_json(base_url, "GET", f"/api/v1/assessment/result/{ids['result']}/report", token=admin_token)
        assert fetched_report["agent_task_id"] == report["agent_task_id"]
        stages.append("能力报告生成与回读")

        link = request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/link-training", {}, admin_token)
        assert link["status"] == "sent", link
        plan_id = int(link["training_plan_json"]["plan_id"])
        ids["plan"] = plan_id
        fetched_link = request_json(base_url, "GET", f"/api/v1/assessment/result/{ids['result']}/training-link", token=admin_token)
        retried_link = request_json(base_url, "POST", f"/api/v1/assessment/result/{ids['result']}/training-link/retry", {}, admin_token)
        assert fetched_link["status"] == "sent" and retried_link["status"] == "sent"
        assert int(retried_link["training_plan_json"]["plan_id"]) == plan_id
        with engine.connect() as connection:
            plan_count = int(connection.execute(text(
                "SELECT COUNT(*) FROM trn_training_plan WHERE id=:id AND talent_id=:talent_id"
            ), {"id": plan_id, "talent_id": talent_id}).scalar() or 0)
            message_count = int(connection.execute(text(
                "SELECT COUNT(*) FROM msg_center WHERE biz_type='assessment_training' AND biz_id=:id"
            ), {"id": ids["result"]}).scalar() or 0)
        assert plan_count == 1 and message_count == 1
        stages.append("培训计划、消息联动与幂等重试")

        print(json.dumps({
            "ok": True,
            "marker": marker,
            "stages": stages,
            "result": {"score": 10, "report_source": report["source"], "training_status": link["status"]},
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        if args.keep_data:
            print(f"Acceptance data retained: {marker}")
        else:
            cleanup(engine, ids, original_talent_level)
            print(f"Acceptance data cleaned: {marker}")


if __name__ == "__main__":
    raise SystemExit(main())
