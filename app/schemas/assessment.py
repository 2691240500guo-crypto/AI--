from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel

QuestionType = Literal["single", "multi", "judge"]


class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)


class QuestionBankUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    status: int | None = Field(default=None, ge=0, le=1)


class QuestionBankOut(ORMModel):
    id: int
    name: str
    description: str
    status: int
    created_at: datetime
    updated_at: datetime


class QuestionCreate(BaseModel):
    bank_id: int = Field(gt=0)
    type: QuestionType
    content: str = Field(min_length=1)
    options: list[Any] | None = None
    answer: list[Any] | str | None = None
    dimension: str = Field(min_length=1, max_length=64)
    difficulty: int = Field(default=1, ge=1, le=5)
    score: Decimal = Field(default=Decimal("1.00"), gt=0, max_digits=10, decimal_places=2)


class QuestionUpdate(BaseModel):
    bank_id: int | None = Field(default=None, gt=0)
    type: QuestionType | None = None
    content: str | None = Field(default=None, min_length=1)
    options: list[Any] | None = None
    answer: list[Any] | str | None = None
    dimension: str | None = Field(default=None, min_length=1, max_length=64)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    score: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    status: int | None = Field(default=None, ge=0, le=1)


class QuestionOut(ORMModel):
    id: int
    bank_id: int
    type: QuestionType
    content: str
    options: list[Any] | None
    answer: list[Any] | str | None
    dimension: str
    difficulty: int
    score: Decimal
    status: int
    created_at: datetime
    updated_at: datetime


class PositionOptionOut(ORMModel):
    id: int
    dept_id: int | None
    name: str
    level: int


class CapabilityRule(BaseModel):
    dimension: str = Field(min_length=1, max_length=64)
    count: int = Field(gt=0, le=500)
    bank_ids: list[int] = Field(default_factory=list)
    types: list[QuestionType] = Field(default_factory=list)
    difficulties: list[int] = Field(default_factory=list)


class CapabilityModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    position_id: int | None = Field(default=None, gt=0)
    position_level: int | None = Field(default=None, ge=1, le=20)
    rules: list[CapabilityRule] = Field(min_length=1, max_length=50)


class CapabilityModelUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    position_id: int | None = Field(default=None, gt=0)
    position_level: int | None = Field(default=None, ge=1, le=20)
    rules: list[CapabilityRule] | None = Field(default=None, min_length=1, max_length=50)
    status: int | None = Field(default=None, ge=0, le=1)


class CapabilityModelOut(ORMModel):
    id: int
    name: str
    description: str
    position_id: int | None
    position_level: int | None
    rules: list[dict] | None
    status: int
    created_at: datetime
    updated_at: datetime


class QuestionImportError(BaseModel):
    row: int
    content: str | None = None
    message: str


class QuestionImportOut(BaseModel):
    total_count: int
    imported_count: int
    failed_count: int
    errors: list[QuestionImportError] = Field(default_factory=list)


class PaperQuestionCreate(BaseModel):
    question_id: int = Field(gt=0)
    sort: int = Field(default=1, ge=1)
    score: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)


class PaperCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=1000)
    bank_ids: list[int] = Field(default_factory=list)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    duration: int = Field(default=60, ge=1, le=1440)
    question_ids: list[int] = Field(default_factory=list)
    random_rule: dict[str, Any] | None = None
    capability_model_id: int | None = Field(default=None, gt=0)


class PaperUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=1000)
    duration: int | None = Field(default=None, ge=1, le=1440)
    status: int | None = Field(default=None, ge=0, le=1)


class LaunchRequest(BaseModel):
    paper_id: int = Field(gt=0)
    talent_ids: list[int] = Field(min_length=1)
    batch_name: str | None = Field(default=None, min_length=1, max_length=128)
    started_at: datetime | None = None
    deadline_at: datetime | None = None


class LaunchResultOut(BaseModel):
    result_id: int
    talent_id: int
    paper_id: int
    batch_id: int
    batch_no: str
    status: int
    started_at: datetime
    deadline_at: datetime


class RandomPaperRule(BaseModel):
    count: int = Field(gt=0, le=500)
    bank_ids: list[int] = Field(default_factory=list)
    types: list[QuestionType] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    difficulties: list[int] = Field(default_factory=list)


class PaperOut(ORMModel):
    id: int
    title: str
    description: str
    bank_ids: list[int] | None
    difficulty: int | None
    total_score: Decimal
    duration: int
    status: int
    generation_mode: str
    capability_model_id: int | None
    generation_rule: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class PaperQuestionOut(ORMModel):
    paper_id: int
    question_id: int
    sort: int
    type_snapshot: QuestionType
    content_snapshot: str
    options_snapshot: list[Any] | None
    dimension_snapshot: str
    score_snapshot: Decimal


class PaperDetailOut(PaperOut):
    questions: list[PaperQuestionOut] = Field(default_factory=list)


class AssessmentResultOut(ORMModel):
    id: int
    talent_id: int
    paper_id: int
    batch_id: int | None
    status: int
    score: Decimal
    correct_count: int
    started_at: datetime | None
    deadline_at: datetime | None
    end_at: datetime | None
    report_source: str | None
    created_at: datetime
    updated_at: datetime


class ResultDetailOut(ORMModel):
    id: int
    result_id: int
    question_id: int
    user_answer: list[Any] | str | None
    is_correct: int
    score: Decimal
    correct_answer: list[Any] | str | None = None
    question_content: str | None = None
    question_type: QuestionType | None = None
    options: list[Any] | None = None
    dimension: str | None = None
    question_score: Decimal | None = None


class AnswerEventOut(ORMModel):
    id: int
    result_id: int
    event_type: str
    detail: str
    source: str
    created_at: datetime


class TrainingOutboxOut(ORMModel):
    id: int
    result_id: int
    agent_task_id: int | None
    weak_dimensions: list[Any] | None
    training_plan_json: dict[str, Any] | None
    status: str
    retry_count: int
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AnswerSaveRequest(BaseModel):
    answers: dict[str, Any] = Field(default_factory=dict)


class AnswerEventCreate(BaseModel):
    event_type: Literal["blur", "focus", "timeout", "leave", "resume", "other"]
    detail: str = Field(default="", max_length=1000)
    source: str = Field(default="admin_h5", max_length=32)


class AnswerQuestionOut(BaseModel):
    question_id: int
    sort: int
    type: QuestionType
    content: str
    options: list[Any] | None
    dimension: str
    score: Decimal
    user_answer: Any = None


class AnswerSnapshotOut(BaseModel):
    result_id: int
    paper_id: int
    talent_id: int
    paper_title: str
    paper_total_score: Decimal
    status: int
    started_at: datetime | None
    deadline_at: datetime | None
    server_time: datetime
    remaining_seconds: int
    answers: dict[str, Any] = Field(default_factory=dict)
    questions: list[AnswerQuestionOut] = Field(default_factory=list)


class SubmitOut(BaseModel):
    result: AssessmentResultOut
    details: list[ResultDetailOut] = Field(default_factory=list)


class AssessmentResultListOut(AssessmentResultOut):
    talent_name: str | None = None
    paper_title: str | None = None
    paper_total_score: Decimal | None = None
    question_count: int = 0
    batch_no: str | None = None
    batch_name: str | None = None


class DimensionStatistic(BaseModel):
    dimension: str
    score: Decimal
    total_score: Decimal
    accuracy: Decimal
    result_count: int = 0
    question_count: int = 0


class AssessmentStatisticsOut(BaseModel):
    total_results: int
    completed_results: int
    average_score: Decimal
    average_rate: Decimal
    pass_count: int
    pass_rate: Decimal
    dimensions: list[DimensionStatistic] = Field(default_factory=list)


class AssessmentBatchOut(ORMModel):
    id: int
    batch_no: str
    name: str
    paper_id: int
    status: int
    started_at: datetime
    deadline_at: datetime
    created_by: int | None
    created_at: datetime
    updated_at: datetime


class AssessmentBatchStatistic(BaseModel):
    batch_id: int
    batch_no: str
    batch_name: str
    paper_id: int
    total_results: int
    completed_results: int
    completion_rate: Decimal
    pass_count: int
    pass_rate: Decimal
    average_score: Decimal


class AssessmentBatchStatisticsOut(BaseModel):
    items: list[AssessmentBatchStatistic] = Field(default_factory=list)


class QuestionStatistic(BaseModel):
    question_id: int
    content: str
    dimension: str
    attempt_count: int
    answered_count: int
    correct_count: int
    accuracy: Decimal
    average_score: Decimal
    total_score: Decimal


class QuestionStatisticsOut(BaseModel):
    items: list[QuestionStatistic] = Field(default_factory=list)


class AssessmentDimensionReport(BaseModel):
    dimension: str
    score: float
    total_score: float
    rate: float
    level: str


class AssessmentReportOut(BaseModel):
    version: str
    result_id: int
    source: Literal["local", "siliconflow"]
    generated_at: datetime
    overall_score: float
    overall_rate: float
    rating: str
    radar: list[AssessmentDimensionReport] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    fallback_reason: str | None = None
    agent_task_id: int | None = None
    level_sync_status: str | None = None
    level_sync_reason: str | None = None


class TrainingLinkOut(ORMModel):
    id: int
    result_id: int
    agent_task_id: int | None
    weak_dimensions: list[Any] | None
    training_plan_json: dict[str, Any] | None
    status: str
    retry_count: int
    error_message: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime
