"""简历上传 / 解析路由（批次 2.3a）。

POST /api/v1/resume/upload   上传简历文件，自动抽出文本 → 创建 talent 草稿
                              返回新 talent id。

后续：
- 批次 2.3b：LLM 抽取 8 字段，更新 talent 与打 AI 标签
- 批次 2.3c：评估报告 + 向量入 Milvus

权限：``talent:list``（与 talent 主档共用）。
仅本模块新增。
"""
# hq新增内容 - 人才档案批次 2.3a
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.dao.talent import TalentDAO
from app.schemas.talent import TalentOut
from app.services.resume_upload_service import ResumeUploadService
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("talent:list"))])


@router.post("/upload", summary="上传简历文件（PDF/Word/图片/TXT/MD），自动抽文本 → 创建 talent 草稿")
async def upload_resume(
    file: UploadFile = File(..., description="PDF/DOCX/图片/TXT/MD"),
    db: Session = Depends(get_db),
):
    """上传后会:
       - 落 MinIO（原件）
       - 抽文本
       - 写 talent(source=import, raw_text=...)
       - 跑规则版自动打标签
       - 返回新 talent（前端可跳转到 /talent/edit/{id} 让用户补字段 / 让批次 2.3b 自动补全）
    """
    if not file.filename:
        from app.utils.response import BusinessError  # 延迟，业务异常
        raise BusinessError(400, "请选择文件")

    content = await file.read()
    if not content:
        from app.utils.response import BusinessError
        raise BusinessError(400, "上传的文件为空")

    obj, duplicate = ResumeUploadService.handle(
        db,
        content=content,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
    )
    return ok({
        "talent": TalentOut.model_validate(obj).model_dump(),
        "message": "简历已上传并入库，可继续在编辑页完善字段",
        # hq+  批次C：去重检测结果（double=确认覆盖 / name|phone=人工审核）
        "duplicate": duplicate,
    })
