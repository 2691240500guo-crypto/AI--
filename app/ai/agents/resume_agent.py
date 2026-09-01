"""Agent① 简历解析（契约见 docs/07-Agent接口契约.md 第 47-60 行）。

统一入口：async def run(input_data) -> dict
    入参: {"file_url": "minio://resumes/2026/09/xxx.pdf" | "http(s)://...", "file_type": "pdf|word|image", "filename"?: "xxx.pdf"}
    返回: {"talent_id": int, "tags": [str], "status": "done"|"failed"}

内部流程（复用 T 域实现，保证与上传接口行为一致）：
    下载文件 → 提取文本 → LLM 抽取结构化字段 → 落库 tal_talent + 自动打标签 → Embedding 入 Milvus talent_vec
    全部由 ResumeUploadService.handle 完成（含 LLM apply 与去重检测）。
"""
from __future__ import annotations

import asyncio
import urllib.request
from typing import Any

from app.utils.logger import logger


async def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """契约：in {file_url, file_type} → out {talent_id, tags, status}。"""
    try:
        file_url: str = input_data["file_url"]
        file_type: str = input_data.get("file_type", "pdf")
        filename: str = input_data.get("filename") or file_url.rstrip("/").split("/")[-1]

        # ---- 1. 下载文件（minio:// 走对象存储，http(s) 走网络）----
        content = await asyncio.to_thread(_download, file_url)
        if not content:
            return {"status": "failed", "error_msg": "文件下载为空"}

        # ---- 2. 解析入库（提取文本 → LLM 抽取 → 落库 → 打标签 → 向量）----
        from app.db.session import SessionLocal
        from app.services.resume_upload_service import ResumeUploadService

        with SessionLocal() as db:
            talent = ResumeUploadService.handle(
                db, content=content, filename=filename,
                content_type=_guess_content_type(file_type),
            )
            db.refresh(talent)
            tags = [rel.tag.name for rel in talent.tag_rels if rel.tag][:20]
            return {"talent_id": talent.id, "tags": tags, "status": "done"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent① 简历解析失败: %s", exc)
        return {"status": "failed", "error_msg": str(exc)}


def _download(file_url: str) -> bytes:
    """按协议下载文件字节。"""
    if file_url.startswith("minio://"):
        from app.utils.object_storage import get_object_storage
        obj_name = file_url[len("minio://"):]
        return get_object_storage().get_bytes(obj_name)
    if file_url.startswith(("http://", "https://")):
        with urllib.request.urlopen(file_url, timeout=60) as resp:  # noqa: S310
            return resp.read()
    # 裸对象键（兼容 object_key 直传）
    from app.utils.object_storage import get_object_storage
    return get_object_storage().get_bytes(file_url)


def _guess_content_type(file_type: str) -> str:
    return {
        "pdf": "application/pdf",
        "word": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image": "application/octet-stream",
    }.get((file_type or "").lower(), "application/octet-stream")
