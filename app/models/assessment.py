from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuestionBank(Base):
    __tablename__ = "asm_question_bank"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[int] = mapped_column(default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    questions = relationship("AssessmentQuestion", back_populates="bank", lazy="selectin")


class AssessmentQuestion(Base):
    __tablename__ = "asm_question"
    __table_args__ = (
        Index("ix_asm_question_bank_status_pair", "bank_id", "status"),
        Index("ix_asm_question_dimension", "dimension"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("asm_question_bank.id", ondelete="RESTRICT"), index=True)
    type: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, default=None)
    answer: Mapped[list | str | None] = mapped_column(JSON, default=None)
    dimension: Mapped[str] = mapped_column(String(64))
    difficulty: Mapped[int] = mapped_column(Integer, default=1)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1.00"))
    status: Mapped[int] = mapped_column(default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    bank = relationship("QuestionBank", back_populates="questions")
    paper_links = relationship("PaperQuestion", back_populates="question")


class AssessmentPaper(Base):
    __tablename__ = "asm_paper"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(1000), default="")
    bank_ids: Mapped[list | None] = mapped_column(JSON, default=None)
    difficulty: Mapped[int | None] = mapped_column(Integer, default=None)
    total_score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    duration: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[int] = mapped_column(default=1, index=True)
    generation_mode: Mapped[str] = mapped_column(String(16), default="manual")
    capability_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("asm_capability_model.id", ondelete="RESTRICT"), default=None, index=True
    )
    generation_rule: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    question_links = relationship("PaperQuestion", back_populates="paper", lazy="selectin")
    results = relationship("AssessmentResult", back_populates="paper")
    batches = relationship("AssessmentBatch", back_populates="paper")
    capability_model = relationship("AssessmentCapabilityModel", back_populates="papers")


class AssessmentCapabilityModel(Base):
    """岗位/职级对应的测评组卷规则。"""

    __tablename__ = "asm_capability_model"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True)
    description: Mapped[str] = mapped_column(String(1000), default="")
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("sys_position.id", ondelete="SET NULL"), default=None, index=True
    )
    position_level: Mapped[int | None] = mapped_column(Integer, default=None, index=True)
    rules: Mapped[list | None] = mapped_column(JSON, default=None)
    status: Mapped[int] = mapped_column(default=1, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    papers = relationship("AssessmentPaper", back_populates="capability_model")


class AssessmentBatch(Base):
    """一次发起测评产生的批次，汇总同一试卷和时间窗口下的结果。"""

    __tablename__ = "asm_assessment_batch"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    paper_id: Mapped[int] = mapped_column(ForeignKey("asm_paper.id", ondelete="RESTRICT"), index=True)
    status: Mapped[int] = mapped_column(Integer, default=1, index=True)
    started_at: Mapped[datetime] = mapped_column()
    deadline_at: Mapped[datetime] = mapped_column()
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("sys_user.id", ondelete="SET NULL"), default=None, index=True
    )
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    paper = relationship("AssessmentPaper", back_populates="batches")
    results = relationship("AssessmentResult", back_populates="batch")


class PaperQuestion(Base):
    __tablename__ = "asm_paper_question"
    __table_args__ = (UniqueConstraint("paper_id", "question_id", name="uq_asm_paper_question"),)

    paper_id: Mapped[int] = mapped_column(
        ForeignKey("asm_paper.id", ondelete="CASCADE"), primary_key=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("asm_question.id", ondelete="RESTRICT"), primary_key=True
    )
    sort: Mapped[int] = mapped_column(Integer, default=1)
    type_snapshot: Mapped[str] = mapped_column(String(16))
    content_snapshot: Mapped[str] = mapped_column(Text)
    options_snapshot: Mapped[list | None] = mapped_column(JSON, default=None)
    answer_snapshot: Mapped[list | str | None] = mapped_column(JSON, default=None)
    dimension_snapshot: Mapped[str] = mapped_column(String(64))
    score_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    paper = relationship("AssessmentPaper", back_populates="question_links")
    question = relationship("AssessmentQuestion", back_populates="paper_links")


class AssessmentResult(Base):
    __tablename__ = "asm_result"
    __table_args__ = (
        Index("ix_asm_result_talent_status", "talent_id", "status"),
        Index("ix_asm_result_paper_status", "paper_id", "status"),
        Index("ix_asm_result_batch_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 人才档案是跨模块统计、等级和培训计划的业务主体；登录账号只用于鉴权和消息投递。
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("sys_user.id", ondelete="RESTRICT"), index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("asm_paper.id", ondelete="RESTRICT"), index=True)
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("asm_assessment_batch.id", ondelete="SET NULL"), default=None, index=True
    )
    status: Mapped[int] = mapped_column(Integer, default=0, index=True)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    deadline_at: Mapped[datetime | None] = mapped_column(default=None, index=True)
    end_at: Mapped[datetime | None] = mapped_column(default=None)
    answer_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    report_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    report_source: Mapped[str | None] = mapped_column(String(32), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    paper = relationship("AssessmentPaper", back_populates="results")
    batch = relationship("AssessmentBatch", back_populates="results")
    details = relationship("AssessmentResultDetail", back_populates="result", lazy="selectin")
    events = relationship("AssessmentAnswerEvent", back_populates="result", lazy="selectin")
    training_outbox = relationship("AssessmentTrainingOutbox", back_populates="result", uselist=False)
    agent_tasks = relationship("AgentTask", back_populates="result")


class AssessmentResultDetail(Base):
    __tablename__ = "asm_result_detail"
    __table_args__ = (UniqueConstraint("result_id", "question_id", name="uq_asm_result_detail"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("asm_result.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("asm_question.id", ondelete="RESTRICT"), index=True)
    user_answer: Mapped[list | str | None] = mapped_column(JSON, default=None)
    is_correct: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"))

    result = relationship("AssessmentResult", back_populates="details")


class AssessmentAnswerEvent(Base):
    __tablename__ = "asm_answer_event"
    __table_args__ = (Index("ix_asm_answer_event_result_type", "result_id", "event_type"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("asm_result.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(32))
    detail: Mapped[str] = mapped_column(String(1000), default="")
    source: Mapped[str] = mapped_column(String(32), default="admin_h5")
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)

    result = relationship("AssessmentResult", back_populates="events")


class AssessmentTrainingOutbox(Base):
    __tablename__ = "asm_training_outbox"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(
        ForeignKey("asm_result.id", ondelete="CASCADE"), unique=True, index=True
    )
    agent_task_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_agent_task.id", ondelete="SET NULL"), default=None, index=True
    )
    weak_dimensions: Mapped[list | None] = mapped_column(JSON, default=None)
    training_plan_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String(1000), default=None)
    processed_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    result = relationship("AssessmentResult", back_populates="training_outbox")
    agent_task = relationship("AgentTask")
