"""智能培训域 TR 数据模型（TR-1 ~ TR-5）。

表前缀 trn_，与需求文档 6.2 对齐。
外键说明：talent_id 引用人才域 tal_talent.id，因并行开发暂不加 FK 约束，
仅存 int + 索引，待 T 域建表后统一补 ForeignKey。
"""
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Course(Base):
    """课程（TR-1）。"""
    __tablename__ = "trn_course"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64), default="", index=True)  # 字典 course_cat
    cover: Mapped[str | None] = mapped_column(String(255), default=None)        # MinIO 对象名
    intro: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(default=0)                               # 学时/学分
    allow_tags: Mapped[str] = mapped_column(String(500), default="")            # 适用短板标签，逗号分隔
    status: Mapped[int] = mapped_column(default=1)                              # 1上架 0下架
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)


class Lesson(Base):
    """课节（TR-1，1 课程 : N 课节）。"""
    __tablename__ = "trn_lesson"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("trn_course.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    content: Mapped[str] = mapped_column(Text, default="")
    file_url: Mapped[str | None] = mapped_column(String(255), default=None)      # 视频/课件 MinIO 对象名
    duration: Mapped[int] = mapped_column(default=0)                             # 时长(分钟)
    sort: Mapped[int] = mapped_column(default=0)


class TrainingPlan(Base):
    """学习计划（TR-2，Agent④/手动生成）。"""
    __tablename__ = "trn_training_plan"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(index=True)  # FK → tal_talent.id（待 T 域建表后补约束）
    title: Mapped[str] = mapped_column(String(128))
    course_ids: Mapped[str] = mapped_column(String(500), default="")             # 逗号分隔课程 id
    source: Mapped[str] = mapped_column(String(16), default="manual")            # agent / manual
    status: Mapped[int] = mapped_column(default=0)                               # 0未开始 1进行中 2已完成
    deadline: Mapped[datetime | None] = mapped_column(default=None)
    generated_by: Mapped[str] = mapped_column(String(64), default="")            # Agent④ / 用户名
    weakness_tags: Mapped[str] = mapped_column(String(500), default="")         # 能力短板/缺口，逗号分隔
    improvement: Mapped[int] = mapped_column(default=0)                 # 提升幅度 0-100（成长轨迹）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)

class LearningRecord(Base):
    """学习进度（TR-2）。"""
    __tablename__ = "trn_learning_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("trn_training_plan.id"), index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("trn_course.id"), index=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("trn_lesson.id"), index=True)
    talent_id: Mapped[int] = mapped_column(index=True)  # FK → tal_talent.id（待 T 域建表后补约束）
    progress: Mapped[int] = mapped_column(default=0)                              # 0-100
    last_lesson_id: Mapped[int] = mapped_column(default=0)
    learned_minutes: Mapped[int] = mapped_column(default=0)    # 实际学习时长（分钟）
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)


class Exam(Base):
    """在线考核（TR-4）。"""
    __tablename__ = "trn_exam"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("trn_training_plan.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    question_ids: Mapped[str] = mapped_column(String(500), default="")            # 逗号分隔题目 id（题目在 A 域）
    pass_score: Mapped[int] = mapped_column(default=60)
    status: Mapped[int] = mapped_column(default=1)                                # 1启用 0停用
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class ExamResult(Base):
    """考核结果（TR-4）。"""
    __tablename__ = "trn_exam_result"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("trn_exam.id"), index=True)
    talent_id: Mapped[int] = mapped_column(index=True)  # FK → tal_talent.id（待 T 域建表后补约束）
    score: Mapped[int] = mapped_column(default=0)
    is_pass: Mapped[int] = mapped_column(default=0)                                # 1通过 0未通过
    answer_json: Mapped[str | None] = mapped_column(Text, default=None)            # 作答详情
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
