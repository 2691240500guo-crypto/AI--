"""在线学习 - 学习进度 DAO（批次3）。"""
# hq新增内容 - 在线学习批次3
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.course_progress import CourseProgress


class CourseProgressDAO(BaseDAO[CourseProgress]):
    __model__ = CourseProgress

    @classmethod
    def get_for_user_course(cls, db: Session, user_id: int, course_id: int) -> CourseProgress | None:
        return db.scalar(
            select(CourseProgress).where(
                CourseProgress.user_id == user_id,
                CourseProgress.course_id == course_id,
            )
        )

    @classmethod
    def list_for_user(cls, db: Session, user_id: int) -> list[CourseProgress]:
        stmt = (
            select(CourseProgress)
            .where(CourseProgress.user_id == user_id)
            .order_by(CourseProgress.updated_at.desc())
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def upsert(cls, db: Session, user_id: int, course_id: int, *,
               position: int, duration: int) -> CourseProgress:
        """记录/更新学习进度（按 user+course 幂等）。"""
        row = cls.get_for_user_course(db, user_id, course_id)
        now = datetime.now()
        if row is None:
            row = CourseProgress(user_id=user_id, course_id=course_id, last_watch_at=now)
            db.add(row)
        row.position = max(0, position)
        if duration:
            row.duration = duration
            row.percent = min(100, round(position * 100 / duration))
            row.completed = 1 if row.percent >= 95 else 0
        row.last_watch_at = now
        db.flush()
        return row
