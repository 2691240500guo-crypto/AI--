"""Agent 调用日志落库（缺口4：ai_agent_task + ai_conversation）。

统一入口，供各问数/对话接口调用：
    - log_agent_task：记录一次 Agent 执行（ai_agent_task，AgentTask 模型已有）
    - log_conversation：记录问答/问数对话（ai_conversation，沿用现有裸 SQL 写法）

落库失败一律静默（不阻塞回复），与 routers/ai.py 既有行为一致。
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.dao.agent import AgentTaskDAO
from app.db.session import SessionLocal


def log_agent_task(agent_code: str, question: str, result: dict[str, Any],
                   chart_type: str | None = None) -> None:
    """记录一次 Agent 执行任务（ai_agent_task）。

    Args:
        agent_code: Agent 代号，如 nl2sql / rag
        question: 用户原始提问
        result: Agent run() 的返回值（含 status/sql/columns/rows/chart_json/error_msg）
        chart_type: 图表类型（可选）
    """
    ok_status = result.get("status") == "done"
    with SessionLocal() as db:
        AgentTaskDAO.create(
            db,
            agent_code=agent_code,
            input_json={"question": question, "chart_type": chart_type},
            output_json={k: result.get(k) for k in ("sql", "columns", "rows", "chart_json")},
            state_json=None,
            status="done" if ok_status else "failed",
            current_node="done" if ok_status else "failed",
            error_msg=result.get("error_msg") if not ok_status else None,
        )
        db.commit()


def log_conversation(user_id: int, conv_type: str, question: str, answer: str,
                     chart_json: Any = None) -> None:
    """记录一次问答/问数对话（ai_conversation）。"""
    with SessionLocal() as db:
        db.execute(
            text(
                "INSERT INTO ai_conversation (user_id, type, question, answer, chart_json, created_at)"
                " VALUES (:user_id, :conv_type, :question, :answer, :chart_json, NOW())"
            ),
            {
                "user_id": user_id,
                "conv_type": conv_type,
                "question": question,
                "answer": answer,
                "chart_json": json.dumps(chart_json, ensure_ascii=False) if chart_json else None,
            },
        )
        db.commit()
