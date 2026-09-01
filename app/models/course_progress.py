"""在线学习 - 学习进度表（批次3 在线学习模块）。

记录某用户对某课程的学习进度：
- ``position``: 已看位置（秒），前端播放器定时上报
- ``duration``: 课程总时长（秒）
- ``completed``: 1=看完（position>=duration*0.95 或手动标记）
- ``last_watch_at``: 最近一次学习时间（进度页「继续学习」排序用）
- 唯一约束 (user_id, course_id)，重复学习只 upsert
"""
# hq新增内容 - 在线学习批次3
from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourseProgress(Base):
    """用户学习进度。"""

    __tablename__ = "tal_course_progress"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_progress_user_course"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("sys_user.id", ondelete="CASCADE"), index=True,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("tal_course.id", ondelete="CASCADE"), index=True,
    )
    position: Mapped[int] = mapped_column(default=0, comment="已看位置（秒）")
    duration: Mapped[int] = mapped_column(default=0, comment="总时长（秒）")
    percent: Mapped[int] = mapped_column(default=0, comment="进度百分比 0-100")
    completed: Mapped[int] = mapped_column(default=0, comment="0学习中/1已完成")
    last_watch_at: Mapped[datetime | None] = mapped_column(default=None, comment="最近学习时间")

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:  # noqa: D401
        return f"<CourseProgress u={self.user_id} c={self.course_id} {self.percent}%>"
