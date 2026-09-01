"""对象存储客户端（MinIO）。

统一封装 MinIO 的桶/文件上传下载能力，供 RAG 文档、个人简历等对象文件使用。
依赖惰性导入，minio 未安装时不影响其它模块。
"""
from __future__ import annotations

from io import BytesIO
from typing import Any

from app.core.config import get_settings


class ObjectStorage:
    """MinIO 对象存储客户端。

    用法：
        from app.utils.object_storage import get_object_storage

        s = get_object_storage()
        s.put_bytes("2026/08/profile_1.pdf", file_bytes, "application/pdf")
        data = s.get_bytes("2026/08/profile_1.pdf")
    """

    def __init__(self) -> None:
        from minio import Minio  # 惰性导入

        settings = get_settings()
        self._client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        self.bucket = settings.MINIO_BUCKET

    def ensure_bucket(self, bucket: str | None = None) -> None:
        """确保默认桶存在，不存在则创建。"""
        name = bucket or self.bucket
        if not self._client.bucket_exists(name):
            self._client.make_bucket(name)

    def put_bytes(self, object_name: str, data: bytes, content_type: str = "application/octet-stream",
                  *, bucket: str | None = None) -> str:
        """上传字节内容，返回对象名称。"""
        name = bucket or self.bucket
        self.ensure_bucket(name)
        self._client.put_object(name, object_name, BytesIO(data), len(data), content_type=content_type)
        return object_name

    def get_bytes(self, object_name: str, *, bucket: str | None = None) -> bytes:
        """下载对象内容为字节。"""
        name = bucket or self.bucket
        resp = self._client.get_object(name, object_name)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    def remove(self, object_name: str, *, bucket: str | None = None) -> None:
        """删除指定对象。"""
        self._client.remove_object(bucket or self.bucket, object_name)

    def list_objects(self, prefix: str = "", *, bucket: str | None = None) -> list[dict[str, Any]]:
        """按前缀列出对象元信息。"""
        name = bucket or self.bucket
        return [
            {"name": obj.object_name, "size": obj.size, "last_modified": obj.last_modified}
            for obj in self._client.list_objects(name, prefix=prefix, recursive=True)
        ]


_object_storage: ObjectStorage | None = None


def get_object_storage() -> ObjectStorage:
    """获取全局单例的对象存储客户端（懒初始化）。"""
    global _object_storage
    if _object_storage is None:
        _object_storage = ObjectStorage()
    return _object_storage
