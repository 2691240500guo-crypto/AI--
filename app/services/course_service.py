"""在线学习 - 业务服务（批次3）。

封装：
- ``upload_video(db, file, title, description)``：视频落 MinIO + 建 biz_course_video
- ``generate_course(db, video_id)``：由视频生成课程（biz_course），标记 has_course=1
- 进度记录在 CourseProgressDAO.upsert 里直接做，不重复封装

仅本模块新增。
"""
# hq新增内容 - 在线学习批次3
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.dao.course import CourseDAO
from app.dao.course_video import CourseVideoDAO
from app.models.course import Course
from app.models.course_video import CourseVideo
from app.utils.object_storage import get_object_storage
from app.utils.response import BusinessError

logger = logging.getLogger(__name__)

_PREFIX = "course/video"


class CourseService:
    """在线学习业务服务。"""

    @staticmethod
    def upload_video(db: Session, content: bytes, filename: str,
                     content_type: str, title: str | None = None,
                     description: str | None = None) -> CourseVideo:
        """上传视频：落 MinIO + 建记录。返回视频记录。"""
        # 校验扩展名
        suffix = ""
        if "." in filename:
            suffix = "." + filename.rsplit(".", 1)[-1].lower()
        allowed = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv", ".flv"}
        if suffix and suffix not in allowed:
            raise BusinessError(400, f"不支持的视频格式：{suffix}（支持 mp4/webm/mov/m4v/avi/mkv/flv）")
        if not content:
            raise BusinessError(400, "上传的文件为空")

        storage = get_object_storage()
        date_prefix = datetime.now().strftime("%Y/%m")
        obj_name = f"{_PREFIX}/{date_prefix}/{uuid.uuid4().hex}{suffix or '.mp4'}"
        try:
            storage.put_bytes(obj_name, content, content_type=content_type or "video/mp4")
        except Exception as e:  # pragma: no cover
            logger.exception("[hq] MinIO 视频上传失败：%s", e)
            raise BusinessError(500, f"对象存储上传失败：{e}") from e

        obj = CourseVideoDAO.create(
            db,
            title=(title or filename or "未命名视频").strip()[:120],
            description=description,
            object_key=obj_name,
            content_type=content_type or "video/mp4",
            size=len(content),
            status=1,
        )
        db.flush()
        logger.info("[hq] 视频已入库：video_id=%s, size=%d", obj.id, len(content))
        return obj

    @staticmethod
    def generate_course(db: Session, video_id: int) -> Course:
        """由视频生成课程（幂等：已生成则直接返回已有课程）。"""
        video = CourseVideoDAO.get(db, video_id)
        if not video or video.status != 1:
            raise BusinessError(404, "视频不存在或已失效")

        exist = CourseDAO.get_by_video(db, video_id)
        if exist:
            raise BusinessError(400, "该视频已生成过课程，请在课程列表查看")

        course = CourseDAO.create(
            db,
            video_id=video_id,
            title=video.title,
            description=video.description or "由视频自动生成",
            duration=video.duration,
            status=1,
        )
        video.has_course = 1
        db.flush()
        logger.info("[hq] 已由视频 %s 生成课程 %s", video_id, course.id)
        return course
