"""在线学习 - 视频 DAO（批次3）。"""
# hq新增内容 - 在线学习批次3
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.course_video import CourseVideo


class CourseVideoDAO(BaseDAO[CourseVideo]):
    __model__ = CourseVideo

    @classmethod
    def list_enabled(cls, db: Session, keyword: str | None = None) -> list[CourseVideo]:
        stmt = select(CourseVideo).where(CourseVideo.status == 1)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(CourseVideo.title.like(like))
        stmt = stmt.order_by(CourseVideo.id.desc())
        return list(db.scalars(stmt).all())
