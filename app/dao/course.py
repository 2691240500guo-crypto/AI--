"""在线学习 - 课程 DAO（批次3）。"""
# hq新增内容 - 在线学习批次3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.course import Course


class CourseDAO(BaseDAO[Course]):
    __model__ = Course

    @classmethod
    def list_enabled(cls, db: Session, keyword: str | None = None) -> list[Course]:
        stmt = select(Course).where(Course.status == 1)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(Course.title.like(like))
        stmt = stmt.order_by(Course.id.desc())
        return list(db.scalars(stmt).all())

    @classmethod
    def get_by_video(cls, db: Session, video_id: int) -> Course | None:
        return db.scalar(select(Course).where(Course.video_id == video_id,
                                              Course.status == 1))
