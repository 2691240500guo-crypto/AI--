"""C06 测评报告和 C07 培训联动服务。"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.agents.assessment_graph import AssessmentGraphRunner
from app.core.config import get_settings
from app.dao.assessment import AssessmentTrainingOutboxDAO
from app.models.assessment import (
    AssessmentResult,
    AssessmentTrainingOutbox,
)


class AssessmentReportService:
    """报告计算、可选 AI 增强和培训 outbox 管理。"""

    @staticmethod
    def _level(rate: float) -> str:
        if rate >= 0.85:
            return "优秀"
        if rate >= 0.70:
            return "良好"
        if rate >= get_settings().ASSESSMENT_PASS_RATE:
            return "合格"
        return "待提升"

    @staticmethod
    def build_local_report(result: AssessmentResult) -> dict:
        detail_by_question = {detail.question_id: detail for detail in result.details}
        dimension_map: dict[str, list[Decimal]] = {}
        for link in result.paper.question_links:
            bucket = dimension_map.setdefault(link.dimension_snapshot, [Decimal("0.00"), Decimal("0.00")])
            bucket[1] += Decimal(str(link.score_snapshot))
            detail = detail_by_question.get(link.question_id)
            if detail:
                bucket[0] += Decimal(str(detail.score))

        radar = []
        for dimension, (score, total_score) in sorted(dimension_map.items()):
            rate = float(score / total_score) if total_score else 0.0
            radar.append({
                "dimension": dimension,
                "score": float(score),
                "total_score": float(total_score),
                "rate": round(rate, 4),
                "level": AssessmentReportService._level(rate),
            })
        strengths = [item["dimension"] for item in radar if item["rate"] >= 0.80]
        weak_threshold = get_settings().ASSESSMENT_WEAK_RATE
        weaknesses = [item["dimension"] for item in radar if item["rate"] < weak_threshold]
        recommendations = [f"建议围绕“{dimension}”安排针对性学习和复测。" for dimension in weaknesses]
        overall_score = float(result.score or 0)
        total_score = float(result.paper.total_score or 0)
        overall_rate = round(overall_score / total_score, 4) if total_score else 0.0
        if not recommendations:
            recommendations = ["保持当前能力水平，结合岗位要求持续复盘和提升。"]
        return {
            "version": "1.0",
            "result_id": result.id,
            "source": "local",
            "generated_at": datetime.now().isoformat(),
            "overall_score": overall_score,
            "overall_rate": overall_rate,
            "rating": AssessmentReportService._level(overall_rate),
            "radar": radar,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "recommendations": recommendations,
            "fallback_reason": None,
        }

    @staticmethod
    def generate(db: Session, result: AssessmentResult) -> dict:
        local_report = AssessmentReportService.build_local_report(result)
        state = AssessmentGraphRunner.run(db, result, local_report)
        return state["report"]

    @staticmethod
    def upsert_training_link(
        db: Session,
        result: AssessmentResult,
        weak_dimensions: list[str],
        training_plan: dict | None = None,
        agent_task_id: int | None = None,
        error_message: str | None = None,
    ):
        link = AssessmentTrainingOutboxDAO.get_by_result(db, result.id)
        if link:
            if link.status == "sent":
                return link, False
            link.agent_task_id = agent_task_id or link.agent_task_id
            link.weak_dimensions = weak_dimensions
            if training_plan is not None:
                link.training_plan_json = training_plan
            link.status = "pending"
            link.error_message = error_message or "培训模块尚未接入，等待后续处理"
            link.processed_at = None
            db.flush()
            return link, False
        link = AssessmentTrainingOutbox(
            result_id=result.id,
            agent_task_id=agent_task_id,
            weak_dimensions=weak_dimensions,
            training_plan_json=training_plan,
            status="pending",
            retry_count=0,
            error_message=error_message or "培训模块尚未接入，等待后续处理",
        )
        db.add(link)
        db.flush()
        return link, True

    @staticmethod
    def ensure_training_link(db: Session, result: AssessmentResult, weak_dimensions: list[str]):
        link, _ = AssessmentReportService.upsert_training_link(
            db, result, weak_dimensions
        )
        return link

    @staticmethod
    def run_training_graph(db: Session, result: AssessmentResult, *, force_notify: bool = False):
        local_report = AssessmentReportService.build_local_report(result)
        state = AssessmentGraphRunner.run(
            db,
            result,
            local_report,
            existing_report=result.report_json or local_report,
            force_notify=force_notify,
        )
        return AssessmentReportService.get_training_link(db, result.id)

    @staticmethod
    def get_training_link(db: Session, result_id: int) -> AssessmentTrainingOutbox:
        link = AssessmentTrainingOutboxDAO.get_by_result(db, result_id)
        if not link:
            raise LookupError("培训联动记录不存在")
        return link

    @staticmethod
    def retry_training_link(db: Session, result: AssessmentResult) -> AssessmentTrainingOutbox:
        link = AssessmentReportService.get_training_link(db, result.id)
        if link.status == "sent":
            return link
        link.retry_count += 1
        db.flush()
        return AssessmentReportService.run_training_graph(db, result, force_notify=True)

    @staticmethod
    def deliver_training_plan(
        db: Session,
        result: AssessmentResult,
        link: AssessmentTrainingOutbox,
        training_plan: dict,
    ) -> AssessmentTrainingOutbox:
        """通过培训域公开 service 落地计划；失败时保留可重试的 outbox。"""
        if link.status == "sent":
            return link
        try:
            from sqlalchemy import select

            from app.models.training import Course
            from app.services.training_service import PlanService

            weaknesses = list(link.weak_dimensions or [])
            courses = list(db.scalars(select(Course).where(Course.status == 1)).all())
            course_ids = [
                course.id for course in courses
                if any(dimension in (course.allow_tags or "") for dimension in weaknesses)
            ][:3]
            plan = PlanService.create(
                db,
                talent_id=result.talent_id,
                title=training_plan.get("title") or "测评短板提升计划",
                course_ids=course_ids,
                deadline=datetime.now() + timedelta(days=30),
                generated_by="assessment",
                weakness_tags=weaknesses,
            )
            link.training_plan_json = {**training_plan, "plan_id": plan.id, "course_ids": course_ids}
            link.status = "sent"
            link.error_message = None
            link.processed_at = datetime.now()
        except Exception as exc:
            link.status = "pending"
            link.error_message = f"培训计划创建失败，可重试：{str(exc)[:900]}"
            link.processed_at = None
        db.flush()
        return link
