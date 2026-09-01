"""智能培训域 TR 出入参 schema。"""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ---------- 课程 / 课节 ----------
class CourseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    category: str = ""
    cover: str | None = None
    intro: str = ""
    score: int = 0
    allow_tags: str = ""
    status: int = 1


class CourseUpdate(BaseModel):
    title: str | None = None
    category: str | None = None
    cover: str | None = None
    intro: str | None = None
    score: int | None = None
    allow_tags: str | None = None
    status: int | None = None


class CourseOut(ORMModel):
    id: int
    title: str
    category: str
    cover: str | None
    intro: str
    score: int
    allow_tags: str
    status: int
    created_at: datetime


class LessonCreate(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    content: str = ""
    file_url: str | None = None
    duration: int = 0
    sort: int = 0


class LessonOut(ORMModel):
    id: int
    course_id: int
    title: str
    content: str
    file_url: str | None
    duration: int
    sort: int


# ---------- 学习计划 / 进度 ----------
class PlanCreate(BaseModel):
    talent_id: int
    title: str
    course_ids: list[int] = []
    deadline: datetime | None = None


class PlanOut(ORMModel):
    id: int
    talent_id: int
    title: str
    course_ids: str
    source: str
    status: int
    deadline: datetime | None
    generated_by: str
    created_at: datetime


class ProgressUpdate(BaseModel):
    course_id: int
    lesson_id: int
    progress: int = Field(ge=0, le=100)


# ---------- 考核 ----------
class ExamCreate(BaseModel):
    plan_id: int
    title: str
    question_ids: list[int] = []
    pass_score: int = 60


class ExamSubmit(BaseModel):
    answers: dict[int, str] = {}   # {question_id: 答案}


class ExamOut(ORMModel):
    id: int
    plan_id: int
    title: str
    question_ids: str
    pass_score: int
    status: int
