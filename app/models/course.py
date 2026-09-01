"""在线学习 - 课程表（批次3 在线学习模块）。

课程由「已上传视频」点击「生成课程」而来：
- ``video_id`` 关联 biz_course_video
- 课程本身不带文件，播放时用关联视频的流接口
- ``status``: 1=上架 / 0=下架
"""
# hq新增内容 - 在线学习批次3
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Course(Base):
    """课程。"""

    __tablename__ = "tal_course"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("tal_course_video.id", ondelete="CASCADE"), index=True,
        comment="关联视频 id",
    )
    title: Mapped[str] = mapped_column(String(128), comment="课程标题（默认取视频标题）")
    description: Mapped[str | None] = mapped_column(Text, default=None, comment="课程简介")
    duration: Mapped[int] = mapped_column(default=0, comment="时长秒（取自视频）")
    status: Mapped[int] = mapped_column(default=1, index=True, comment="1上架/0下架")

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:  # noqa: D401
        return f"<Course {self.id} {self.title!r}>"
