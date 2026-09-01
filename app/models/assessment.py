"""智能测评域模型：题库、题目、试卷、批次、作答明细。
表前缀 asm_，对应 01-需求分析 4.2。
"""
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, PrimaryKeyConstraint, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QuestionBank(Base):
    """题库（A-1）。"""
    __tablename__ = "asm_question_bank"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[int] = mapped_column(default=1)  # 1启用 0停用
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    questions: Mapped[list["Question"]] = relationship(
        back_populates="bank", cascade="all, delete-orphan", lazy="selectin"
    )


class Question(Base):
    """题目（A-1）。

    type: single 单选 / multi 多选 / judge 判断
    options: JSON 字符串，结构 [{\"key\":\"A\",\"text\":\"...\"}, ...]
    answer: 单选用 \"A\"，多选用 \"A,B\"，判断用 \"true\"/\"false\"
    """
    __tablename__ = "asm_question"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bank_id: Mapped[int] = mapped_column(ForeignKey("asm_question_bank.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(16), default="single")
    content: Mapped[str] = mapped_column(Text)
    options: Mapped[str | None] = mapped_column(Text, default=None)  # JSON
    answer: Mapped[str] = mapped_column(String(64))
    dimension: Mapped[str | None] = mapped_column(String(32), default=None, index=True)
    difficulty: Mapped[int] = mapped_column(default=1)  # 1-5
    score: Mapped[int] = mapped_column(default=10)
    status: Mapped[int] = mapped_column(default=1)  # 1启用 0停用
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    bank: Mapped[QuestionBank] = relationship(back_populates="questions")


class Paper(Base):
    """试卷（A-2）。"""
    __tablename__ = "asm_paper"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    difficulty: Mapped[int] = mapped_column(default=1)  # 1-5
    total_score: Mapped[int] = mapped_column(default=100)
    duration: Mapped[int] = mapped_column(default=60)  # 时限（分钟），需求文档 duration(min)
    generation_mode: Mapped[str] = mapped_column(String(16), default="manual")  # 组卷方式 manual/auto
    status: Mapped[int] = mapped_column(default=1)  # 1启用 0停用
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    items: Mapped[list["PaperQuestion"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan",
        lazy="selectin", order_by="PaperQuestion.sort"
    )


class PaperQuestion(Base):
    """试卷-题目中间表（A-2），复合主键对齐需求文档 4.2（paper_id+question_id）。"""
    __tablename__ = "asm_paper_question"
    __table_args__ = (PrimaryKeyConstraint("paper_id", "question_id"),)

    paper_id: Mapped[int] = mapped_column(ForeignKey("asm_paper.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("asm_question.id", ondelete="CASCADE"), index=True)
    sort: Mapped[int] = mapped_column(default=0)

    paper: Mapped[Paper] = relationship(back_populates="items")
    question: Mapped[Question] = relationship(lazy="joined")


class Result(Base):
    """测评批次（A-3/4/5）。"""
    __tablename__ = "asm_result"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("asm_paper.id"), index=True)
    status: Mapped[int] = mapped_column(default=0)  # 0未答 1答题中 2已交卷 3已出报告
    score: Mapped[int] = mapped_column(default=0)
    correct_count: Mapped[int] = mapped_column(default=0)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    end_at: Mapped[datetime | None] = mapped_column(default=None)
    # 作答内容：[{question_id, user_answer}, ...] JSON
    answer_json: Mapped[str | None] = mapped_column(Text, default=None)
    # Agent② 报告（stub）：雷达/短板/优势/评级 JSON
    report_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    paper: Mapped[Paper] = relationship(lazy="selectin")
    details: Mapped[list["ResultDetail"]] = relationship(
        back_populates="result", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def total_count(self) -> int:
        """总题数（需求文档/表无此列，由作答明细派生，兼容前端展示）。"""
        return len(self.details)


class ResultDetail(Base):
    """作答明细（A-4/5）。"""
    __tablename__ = "asm_result_detail"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("asm_result.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("asm_question.id"), index=True)
    user_answer: Mapped[str | None] = mapped_column(String(64), default=None)
    is_correct: Mapped[int] = mapped_column(default=0)  # 1正确 0错误
    score: Mapped[int] = mapped_column(default=0)

    result: Mapped[Result] = relationship(back_populates="details")
    question: Mapped[Question] = relationship(lazy="joined")
