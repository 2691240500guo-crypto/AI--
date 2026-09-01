"""在线学习 - 视频表（批次3 在线学习模块）。

存储已上传的视频元信息（视频字节存 MinIO，本表只存 object_key 等元数据）。
- ``status``: 1=正常 / 0=失效（软删）
- ``has_course``: 0=未生成课程 / 1=已生成课程（前端「生成课程」按钮据此展示）
"""
# hq新增内容 - 在线学习批次3
from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourseVideo(Base):
    """已上传视频。"""

    __tablename__ = "tal_course_video"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), comment="视频标题")
    description: Mapped[str | None] = mapped_column(Text, default=None, comment="视频简介")
    object_key: Mapped[str] = mapped_column(String(256), index=True, comment="MinIO 对象键")
    content_type: Mapped[str | None] = mapped_column(String(64), default=None, comment="视频 MIME")
    size: Mapped[int] = mapped_column(default=0, comment="字节数")
    duration: Mapped[int] = mapped_column(default=0, comment="时长（秒），未解析为 0")
    cover_key: Mapped[str | None] = mapped_column(String(256), default=None, comment="封面图 MinIO 键（可选）")
    has_course: Mapped[int] = mapped_column(default=0, comment="0未生成课程/1已生成")
    status: Mapped[int] = mapped_column(default=1, index=True, comment="1正常/0失效")

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:  # noqa: D401
        return f"<CourseVideo {self.id} {self.title!r}>"
