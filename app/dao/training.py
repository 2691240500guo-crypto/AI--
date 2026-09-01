"""智能培训域 TR 数据访问层。"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.training import (Course, Exam, ExamResult, LearningRecord,
                                 Lesson, TrainingPlan)


class CourseDAO(BaseDAO[Course]):
    __model__ = Course

    @classmethod
    def paged(cls, db: Session, keyword: str | None = None, category: str | None = None,
              status: int | None = None, page: int = 1, page_size: int = 20) -> list[Course]:
        stmt = select(Course)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(Course.title.like(like))
        if category:
            stmt = stmt.where(Course.category == category)
        if status is not None:
            stmt = stmt.where(Course.status == status)
        stmt = stmt.order_by(Course.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())

    @classmethod
    def count(cls, db: Session, keyword: str | None = None, category: str | None = None,
              status: int | None = None) -> int:
        stmt = select(func.count()).select_from(Course)
        if keyword:
            stmt = stmt.where(Course.title.like(f"%{keyword}%"))
        if category:
            stmt = stmt.where(Course.category == category)
        if status is not None:
            stmt = stmt.where(Course.status == status)
        return db.scalar(stmt) or 0


class LessonDAO(BaseDAO[Lesson]):
    __model__ = Lesson


class PlanDAO(BaseDAO[TrainingPlan]):
    __model__ = TrainingPlan


class RecordDAO(BaseDAO[LearningRecord]):
    __model__ = LearningRecord


class ExamDAO(BaseDAO[Exam]):
    __model__ = Exam


class ExamResultDAO(BaseDAO[ExamResult]):
    __model__ = ExamResult
