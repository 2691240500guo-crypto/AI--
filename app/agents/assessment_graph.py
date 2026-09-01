"""C 智能测评的 LangGraph 报告与培训联动流程。"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from app.agents.assessment_agent import AssessmentAgent
from app.agents.training_agent import TrainingAgent
from app.core.config import get_settings
from app.dao.agent import AgentTaskDAO
from app.models.assessment import AssessmentResult
from app.models.user import User
from app.services.message_service import MessageService


class AssessmentAgentState(TypedDict, total=False):
    task_id: int
    result_id: int
    talent_id: int
    local_report: dict[str, Any]
    report: dict[str, Any]
    ai_report: dict[str, Any]
    talent_context: dict[str, Any]
    capability_context: dict[str, Any]
    training_plan: dict[str, Any]
    training_link_id: int
    training_link_status: str
    current_node: str
    validation_ok: bool
    analysis_error: str | None
    validation_error: str | None
    training_error: str | None
    level_sync_status: str
    level_sync_reason: str | None
    retry_count: int
    force_notify: bool
    notify_required: bool
    notify_status: str


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


class AssessmentGraphRunner:
    """为一次报告生成或培训重试构建独立图实例。"""

    MAX_RETRIES = 2

    @classmethod
    def run(
        cls,
        db: Session,
        result: AssessmentResult,
        local_report: dict[str, Any],
        *,
        existing_report: dict[str, Any] | None = None,
        force_notify: bool = False,
    ) -> AssessmentAgentState:
        task = AgentTaskDAO.create(
            db,
            agent_code="assessment",
            result_id=result.id,
            input_json={
                "result_id": result.id,
                "talent_id": result.talent_id,
                "paper_id": result.paper_id,
            },
            status="running",
            state_json={"current_node": "created", "result_id": result.id},
            current_node="created",
            retry_count=0,
        )
        initial: AssessmentAgentState = {
            "task_id": task.id,
            "result_id": result.id,
            "talent_id": result.talent_id,
            "local_report": local_report,
            "report": existing_report or {},
            "retry_count": 0,
            "force_notify": force_notify,
        }
        graph = cls._build_graph(db, result, task)
        try:
            final_state = graph.invoke(initial)
        except Exception as exc:
            task.status = "failed"
            task.error_msg = str(exc)[:1000]
            task.current_node = "failed"
            task.state_json = _json_safe({**initial, "current_node": "failed", "error": str(exc)})
            db.flush()
            raise
        return final_state

    @classmethod
    def _build_graph(cls, db: Session, result: AssessmentResult, task):
        workflow = StateGraph(AssessmentAgentState)

        def checkpoint(name: str, state: AssessmentAgentState, updates: dict[str, Any]) -> dict[str, Any]:
            merged = {**state, **updates, "current_node": name}
            task.current_node = name
            task.retry_count = int(merged.get("retry_count", 0))
            task.state_json = _json_safe(merged)
            db.flush()
            return {**updates, "current_node": name}

        def node(name: str, handler):
            def wrapped(state: AssessmentAgentState):
                return checkpoint(name, state, handler(state))
            return wrapped

        def load_context(state: AssessmentAgentState) -> dict[str, Any]:
            talent = db.get(User, result.talent_id)
            paper = result.paper
            return {
                "talent_context": {
                    "talent_id": result.talent_id,
                    "nickname": talent.nickname if talent else None,
                    "username": talent.username if talent else None,
                },
                "capability_context": {
                    "paper_id": result.paper_id,
                    "paper_title": paper.title,
                    "generation_rule": paper.generation_rule,
                },
            }

        def analyze_assessment(state: AssessmentAgentState) -> dict[str, Any]:
            try:
                report = AssessmentAgent.enhance(
                    state["local_report"],
                    {
                        "talent": state.get("talent_context", {}),
                        "capability": state.get("capability_context", {}),
                    },
                )
                return {"ai_report": report, "analysis_error": None}
            except Exception as exc:
                return {
                    "ai_report": {},
                    "analysis_error": str(exc)[:1000],
                    "retry_count": state.get("retry_count", 0) + 1,
                }

        def repair_report(state: AssessmentAgentState) -> dict[str, Any]:
            return {"validation_error": "上一轮报告未通过结构校验，要求模型仅返回合法 JSON。"}

        def validate_report(state: AssessmentAgentState) -> dict[str, Any]:
            ai_report = state.get("ai_report") or {}
            if not ai_report:
                return {"validation_ok": False}
            try:
                AssessmentAgent.validate(ai_report)
                report = dict(state["local_report"])
                report.update(ai_report)
                report.update({"source": "siliconflow", "fallback_reason": None})
                return {"validation_ok": True, "report": report, "validation_error": None}
            except Exception as exc:
                return {
                    "validation_ok": False,
                    "validation_error": str(exc)[:1000],
                    "retry_count": state.get("retry_count", 0) + 1,
                }

        def fallback_report(state: AssessmentAgentState) -> dict[str, Any]:
            report = dict(state["local_report"])
            report["source"] = "local"
            report["fallback_reason"] = state.get("analysis_error") or state.get("validation_error")
            return {"report": report}

        def persist_report(state: AssessmentAgentState) -> dict[str, Any]:
            report = dict(state["report"])
            report["agent_task_id"] = task.id
            result.report_json = report
            result.report_source = report.get("source", "local")
            result.status = 3
            db.flush()
            return {"report": report}

        def sync_talent_level(state: AssessmentAgentState) -> dict[str, Any]:
            report = dict(state["report"])
            reason = "当前仓库未提供人才档案公开 service，等级保存在测评报告中等待回写。"
            report["level_sync_status"] = "pending"
            report["level_sync_reason"] = reason
            result.report_json = report
            db.flush()
            return {
                "report": report,
                "level_sync_status": "pending",
                "level_sync_reason": reason,
            }

        def build_training_plan(state: AssessmentAgentState) -> dict[str, Any]:
            weaknesses = list((state.get("report") or state["local_report"]).get("weaknesses", []))
            try:
                plan = TrainingAgent.generate(
                    weaknesses,
                    {
                        "talent": state.get("talent_context", {}),
                        "capability": state.get("capability_context", {}),
                    },
                )
                return {"training_plan": plan, "training_error": None}
            except Exception as exc:
                plan = TrainingAgent.build_local_plan(weaknesses)
                plan["fallback_reason"] = str(exc)[:1000]
                return {"training_plan": plan, "training_error": str(exc)[:1000]}

        def persist_training_link(state: AssessmentAgentState) -> dict[str, Any]:
            from app.services.assessment_report_service import AssessmentReportService

            report = state.get("report") or state["local_report"]
            link, created = AssessmentReportService.upsert_training_link(
                db,
                result,
                report.get("weaknesses", []),
                state.get("training_plan"),
                task.id,
                state.get("training_error"),
            )
            return {
                "training_link_id": link.id,
                "training_link_status": link.status,
                "notify_required": created or state.get("force_notify", False),
            }

        def notify(state: AssessmentAgentState) -> dict[str, Any]:
            if not state.get("notify_required"):
                return {"notify_status": "skipped"}
            plan = state.get("training_plan") or {}
            courses = plan.get("courses") or []
            course_text = "；".join(str(course.get("title", "")) for course in courses if isinstance(course, dict))
            try:
                with db.begin_nested():
                    MessageService.send(
                        db,
                        type_code="train",
                        title="测评培训计划已生成",
                        content=course_text or "请查看测评短板提升计划。",
                        sender_id=None,
                        receiver_ids=[result.talent_id],
                        biz_type="assessment_training",
                        biz_id=result.id,
                    )
                return {"notify_status": "sent"}
            except Exception as exc:
                return {"notify_status": "failed", "training_error": str(exc)[:1000]}

        def finalize(state: AssessmentAgentState) -> dict[str, Any]:
            task.status = "done"
            task.error_msg = state.get("training_error")
            task.output_json = _json_safe({
                "report": state.get("report"),
                "training_plan": state.get("training_plan"),
                "training_link_id": state.get("training_link_id"),
                "level_sync_status": state.get("level_sync_status"),
                "notify_status": state.get("notify_status"),
            })
            return {}

        def after_context(state: AssessmentAgentState) -> str:
            return "build_training_plan" if state.get("report", {}).get("result_id") else "analyze_assessment"

        def after_validation(state: AssessmentAgentState) -> str:
            if state.get("validation_ok"):
                return "persist_report"
            error = state.get("analysis_error") or ""
            if "未配置硅基流动" in error or state.get("retry_count", 0) >= cls.MAX_RETRIES:
                return "fallback_report"
            return "repair_report"

        workflow.add_node("load_context", node("load_context", load_context))
        workflow.add_node("analyze_assessment", node("analyze_assessment", analyze_assessment))
        workflow.add_node("repair_report", node("repair_report", repair_report))
        workflow.add_node("validate_report", node("validate_report", validate_report))
        workflow.add_node("fallback_report", node("fallback_report", fallback_report))
        workflow.add_node("persist_report", node("persist_report", persist_report))
        workflow.add_node("sync_talent_level", node("sync_talent_level", sync_talent_level))
        workflow.add_node("build_training_plan", node("build_training_plan", build_training_plan))
        workflow.add_node("persist_training_link", node("persist_training_link", persist_training_link))
        workflow.add_node("notify", node("notify", notify))
        workflow.add_node("finalize", node("finalize", finalize))

        workflow.set_entry_point("load_context")
        workflow.add_conditional_edges("load_context", after_context, {
            "analyze_assessment": "analyze_assessment",
            "build_training_plan": "build_training_plan",
        })
        workflow.add_edge("analyze_assessment", "validate_report")
        workflow.add_conditional_edges("validate_report", after_validation, {
            "persist_report": "persist_report",
            "repair_report": "repair_report",
            "fallback_report": "fallback_report",
        })
        workflow.add_edge("repair_report", "analyze_assessment")
        workflow.add_edge("fallback_report", "persist_report")
        workflow.add_edge("persist_report", "sync_talent_level")
        workflow.add_edge("sync_talent_level", "build_training_plan")
        workflow.add_edge("build_training_plan", "persist_training_link")
        workflow.add_edge("persist_training_link", "notify")
        workflow.add_edge("notify", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()
