from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  注册完整 metadata
from app.agents.training_agent import TrainingAgent
from app.db.base import Base
from app.models.assessment import (
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentResult,
    PaperQuestion,
    QuestionBank,
)
from app.models.message import Message
from app.models.talent import Talent
from app.models.training import TrainingPlan
from app.models.user import User
from app.services.assessment_report_service import AssessmentReportService
from app.services.message_service import MessageService


@pytest.fixture
def training_db(tmp_path):
    database = tmp_path / "assessment-training-link.db"
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        talent = Talent(name="联动测试人才", status=1)
        db.add(talent)
        db.flush()
        user = User(
            username="training-link-user",
            password="not-used-in-test",
            nickname="联动测试账号",
            talent_id=talent.id,
            user_type="employee",
            status=1,
        )
        bank = QuestionBank(name="联动测试题库", status=1)
        db.add_all([user, bank])
        db.flush()
        question = AssessmentQuestion(
            bank_id=bank.id,
            type="single",
            content="测试题目",
            options=["A", "B"],
            answer="A",
            dimension="沟通能力",
            difficulty=1,
            score=Decimal("10.00"),
            status=1,
        )
        paper = AssessmentPaper(
            title="联动测试试卷",
            total_score=Decimal("10.00"),
            duration=60,
            status=1,
        )
        db.add_all([question, paper])
        db.flush()
        db.add(PaperQuestion(
            paper_id=paper.id,
            question_id=question.id,
            sort=1,
            type_snapshot="single",
            content_snapshot=question.content,
            options_snapshot=question.options,
            answer_snapshot=question.answer,
            dimension_snapshot=question.dimension,
            score_snapshot=question.score,
        ))
        result = AssessmentResult(
            talent_id=talent.id,
            user_id=user.id,
            paper_id=paper.id,
            status=3,
            score=Decimal("0.00"),
            correct_count=0,
            report_source="local",
        )
        db.add(result)
        db.flush()
        result.report_json = {
            "version": "1.0",
            "result_id": result.id,
            "source": "local",
            "overall_score": 0,
            "overall_rate": 0,
            "rating": "待提升",
            "radar": [],
            "strengths": [],
            "weaknesses": ["沟通能力"],
            "recommendations": ["安排沟通训练"],
        }
        db.commit()
        yield db, result
    engine.dispose()


@pytest.fixture(autouse=True)
def deterministic_training_plan(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        TrainingAgent,
        "generate",
        staticmethod(
            lambda weak_dimensions, context=None: TrainingAgent.build_local_plan(weak_dimensions)
        ),
    )


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_sqlite_chain_sends_plan_even_when_no_course_matches(training_db):
    db, result = training_db

    link = AssessmentReportService.run_training_graph(db, result)
    db.commit()

    plan = db.scalar(select(TrainingPlan))
    assert plan is not None
    assert plan.talent_id == result.talent_id
    assert plan.course_ids == ""
    assert link.status == "sent"
    assert link.error_message is None
    assert link.processed_at is not None
    assert link.training_plan_json["plan_id"] == plan.id
    assert link.training_plan_json["course_ids"] == []
    assert _count(db, Message) == 1


def test_missing_training_plan_table_marks_link_failed_and_retryable(training_db):
    db, result = training_db
    TrainingPlan.__table__.drop(db.get_bind())

    link = AssessmentReportService.run_training_graph(db, result)
    db.commit()

    assert link.status == "failed"
    assert link.processed_at is None
    assert "培训计划创建失败，可重试" in link.error_message
    assert _count(db, Message) == 0


def test_message_failure_retry_reuses_plan_and_sent_retry_is_idempotent(
    training_db,
    monkeypatch: pytest.MonkeyPatch,
):
    db, result = training_db
    original_send = MessageService.send.__func__
    attempts = 0

    def fail_once(cls, session, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("simulated message failure")
        return original_send(cls, session, **kwargs)

    monkeypatch.setattr(MessageService, "send", classmethod(fail_once))

    failed_link = AssessmentReportService.run_training_graph(db, result)
    db.commit()
    saved_plan_id = failed_link.training_plan_json["plan_id"]

    assert failed_link.status == "failed"
    assert "培训消息发送失败，可重试" in failed_link.error_message
    assert _count(db, TrainingPlan) == 1
    assert _count(db, Message) == 0

    sent_link = AssessmentReportService.retry_training_link(db, result)
    db.commit()

    assert sent_link.status == "sent"
    assert sent_link.retry_count == 1
    assert sent_link.training_plan_json["plan_id"] == saved_plan_id
    assert _count(db, TrainingPlan) == 1
    assert _count(db, Message) == 1

    same_link = AssessmentReportService.retry_training_link(db, result)
    db.commit()

    assert same_link.id == sent_link.id
    assert same_link.status == "sent"
    assert same_link.retry_count == 1
    assert attempts == 2
    assert _count(db, TrainingPlan) == 1
    assert _count(db, Message) == 1
