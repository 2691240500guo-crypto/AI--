"""智能测评域 Pydantic 出入参。

question.options 在数据库存为 JSON 字符串，schema 用 list[dict] 对外暴露。
question.answer / result_detail.user_answer 用统一格式：
  - 单选：选项 key，如 "A"
  - 多选：逗号分隔，按 key 字典序排序，如 "A,B"
  - 判断：字符串 "true" / "false"
"""
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel


# ---------- 题库 ----------

class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    status: int = Field(default=1, ge=0, le=1)


class QuestionBankUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: int | None = Field(default=None, ge=0, le=1)


class QuestionBankOut(ORMModel):
    id: int
    name: str
    description: str | None
    status: int
    question_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------- 题目 ----------

class QuestionOption(BaseModel):
    key: str = Field(min_length=1, max_length=8)
    text: str = Field(min_length=1)


class QuestionCreate(BaseModel):
    bank_id: int
    type: Literal["single", "multi", "judge"] = "single"
    content: str = Field(min_length=1)
    options: list[QuestionOption] | None = None  # judge 题可不传
    answer: str = Field(min_length=1, max_length=64)
    dimension: str | None = Field(default=None, max_length=32)
    difficulty: int = Field(default=1, ge=1, le=5)
    score: int = Field(default=10, ge=0)
    status: int = Field(default=1, ge=0, le=1)

    @field_validator("answer")
    @classmethod
    def _normalize_answer(cls, v: str, info) -> str:
        v = v.strip()
        if info.data.get("type") == "multi":
            parts = sorted({p.strip().upper() for p in v.split(",") if p.strip()})
            if not parts:
                raise ValueError("多选题答案不能为空")
            return ",".join(parts)
        if info.data.get("type") == "judge":
            if v.lower() not in {"true", "false"}:
                raise ValueError("判断题答案只能是 true/false")
            return v.lower()
        return v.upper()


class QuestionUpdate(BaseModel):
    type: Literal["single", "multi", "judge"] | None = None
    content: str | None = None
    options: list[QuestionOption] | None = None
    answer: str | None = None
    dimension: str | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    score: int | None = Field(default=None, ge=0)
    status: int | None = Field(default=None, ge=0, le=1)


class QuestionOut(ORMModel):
    id: int
    bank_id: int
    type: str
    content: str
    options: list[dict] | None = None
    answer: str
    dimension: str | None
    difficulty: int
    score: int
    status: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, obj, *, with_answer: bool = True):
        opts = None
        if obj.options:
            try:
                opts = json.loads(obj.options)
            except Exception:
                opts = None
        return cls.model_validate({
            "id": obj.id, "bank_id": obj.bank_id, "type": obj.type, "content": obj.content,
            "options": opts, "answer": obj.answer if with_answer else "",
            "dimension": obj.dimension, "difficulty": obj.difficulty, "score": obj.score,
            "status": obj.status, "created_at": obj.created_at, "updated_at": obj.updated_at,
        })


# ---------- 试卷 ----------

class PaperCreate(BaseModel):
    """手动组卷：传 question_ids 自动算 total_score / duration 可后续改。"""
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    question_ids: list[int] = Field(default_factory=list, max_length=200)
    difficulty: int = Field(default=1, ge=1, le=5)
    duration: int = Field(default=60, ge=1, le=600)
    generation_mode: str = Field(default="manual", pattern="^(manual|auto)$")
    status: int = Field(default=1, ge=0, le=1)


class PaperAutoCreate(BaseModel):
    """智能抽题组卷：按维度/难度/题数条件自动选题。"""
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    dimension: str | None = Field(default=None, max_length=32)   # 能力维度，空=不限
    difficulty: int | None = Field(default=None, ge=1, le=5)      # 难度，空=不限
    question_count: int = Field(default=10, ge=1, le=100)         # 题数
    duration: int = Field(default=60, ge=1, le=600)
    status: int = Field(default=1, ge=0, le=1)


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    question_ids: list[int] | None = None
    difficulty: int | None = Field(default=None, ge=1, le=5)
    duration: int | None = Field(default=None, ge=1, le=600)
    generation_mode: str | None = Field(default=None, pattern="^(manual|auto)$")
    status: int | None = Field(default=None, ge=0, le=1)


class PaperOut(ORMModel):
    id: int
    title: str
    description: str | None
    difficulty: int
    total_score: int
    duration: int
    generation_mode: str = "manual"
    status: int
    question_count: int = 0
    created_at: datetime
    updated_at: datetime


class PaperDetailOut(PaperOut):
    questions: list[QuestionOut] = Field(default_factory=list)


# ---------- 发起测评 ----------

class LaunchRequest(BaseModel):
    paper_id: int
    talent_ids: list[int] = Field(min_length=1, max_length=500)


class LaunchResultItem(BaseModel):
    result_id: int
    talent_id: int
    talent_name: str | None = None
    paper_id: int
    status: int


class LaunchResponse(BaseModel):
    paper_id: int
    launched_count: int
    items: list[LaunchResultItem]


# ---------- 作答 / 判分 ----------

class AnswerItem(BaseModel):
    question_id: int
    user_answer: str = Field(min_length=1, max_length=64)


class SubmitRequest(BaseModel):
    answers: list[AnswerItem] = Field(min_length=1)


class ResultDetailOut(ORMModel):
    id: int
    question_id: int
    user_answer: str | None
    is_correct: int
    score: int
    question: QuestionOut | None = None

    @classmethod
    def from_model(cls, obj, *, with_answer: bool = False):
        return cls(
            id=obj.id, question_id=obj.question_id, user_answer=obj.user_answer,
            is_correct=obj.is_correct, score=obj.score,
            question=QuestionOut.from_model(obj.question, with_answer=with_answer)
            if obj.question else None,
        )


class ResultOut(ORMModel):
    id: int
    talent_id: int
    paper_id: int
    status: int
    score: int
    correct_count: int
    total_count: int
    started_at: datetime | None
    end_at: datetime | None
    created_at: datetime


class ResultDetailResultOut(ResultOut):
    details: list[ResultDetailOut] = Field(default_factory=list)


class ReportStubOut(BaseModel):
    """Agent② 报告 stub：MVP 不接 LangGraph，返回结构化占位。"""
    result_id: int
    level: str  # S/A/B/C
    radar: dict  # {维度: 0-100}
    strengths: list[str]
    weaknesses: list[str]
    suggestions: list[str]
    summary: str


# ---------- 待测列表 / 答题视图 ----------

class TodoItemOut(BaseModel):
    """某人才待测 / 答题中 / 待阅的批次。"""
    result_id: int
    paper_id: int
    paper_title: str
    duration: int
    total_score: int
    status: int
    question_count: int
    created_at: datetime


class AnswerViewQuestion(BaseModel):
    id: int
    type: str
    content: str
    options: list[dict] | None = None
    score: int
    dimension: str | None = None
    sort: int


class AnswerViewOut(BaseModel):
    """答题视图：不返回正确答案。"""
    result_id: int
    paper_id: int
    paper_title: str
    duration: int
    total_score: int
    status: int
    questions: list[AnswerViewQuestion]
    previous_answers: list[AnswerItem] = Field(default_factory=list)
