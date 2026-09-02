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
    video_id: int | None = None          # 挂接 tal_course_video：培训课节=视频
    duration: int = 0
    sort: int = 0


class LessonOut(ORMModel):
    id: int
    course_id: int
    title: str
    content: str
    file_url: str | None
    video_id: int | None = None          # 关联 tal_course_video，前端可播 /course/videos/{id}/stream
    video_url: str | None = None         # 由 router 组装视频流地址
    duration: int
    sort: int


# ---------- 学习计划 / 进度 ----------
class PlanCreate(BaseModel):
    talent_id: int
    title: str
    course_ids: list[int] = []
    deadline: datetime | None = None
    weakness_tags: list[str] = []
    # 管理端补充（可选）
    status: int | None = None              # 0未开始 1进行中 2已完成 3已逾期
    generated_by: str | None = None
    improvement: int | None = None


class PlanOut(ORMModel):
    id: int
    talent_id: int
    title: str
    course_ids: str
    source: str
    status: int
    deadline: datetime | None
    generated_by: str
    weakness_tags: str
    improvement: int
    created_at: datetime


class ProgressUpdate(BaseModel):
    course_id: int
    lesson_id: int = 0            # 0=未知课节，后端自动取该课程第一节兜底
    progress: int = Field(ge=0, le=100)
    learned_minutes: int = 0


class PlanUpdate(BaseModel):
    """计划基本信息更新（管理端编辑）。"""
    title: str | None = None
    course_ids: list[int] | None = None
    weakness_tags: list[str] | None = None
    status: int | None = None          # 0未开始 1进行中 2已完成
    deadline: datetime | None = None
    generated_by: str | None = None
    improvement: int | None = None


class LessonSyncItem(LessonCreate):
    """课节同步条目：带 id 表示更新已有课节，无 id 表示新增。"""
    id: int | None = None


class LessonSyncIn(BaseModel):
    """课节全量同步：带 id 的更新、无 id 的新增、缺席的删除。"""
    lessons: list[LessonSyncItem] = []


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


# ---------- Agent④ 推荐（TR-3） ----------
class AgentRecommend(BaseModel):
    talent_id: int
    shortages: list[str] = Field(default_factory=list)  # 契约字段为 shortcomings，兼容别名
    position_ids: list[int] = Field(default_factory=list)  # 岗位能力预留，M 域完成后接入
    course_ids: list[int] = Field(default_factory=list)  # ★ 确认生成时传入已选课程
    title: str = "个性化培训计划"
    deadline: datetime | None = None
    push: bool = True
