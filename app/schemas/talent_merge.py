"""去重审核 schema（批次 C）。"""
# hq新增内容 - 人才档案批次C
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TalentMergeOut(BaseModel):
    """去重审核记录出参（含新旧档案快照，前端列表直接渲染）。"""
    id: int
    new_talent_id: int
    old_talent_id: int
    match_type: str
    status: str
    remark: str | None = None
    created_at: datetime

    # 新档案快照
    new_name: str = ""
    new_phone: str | None = None
    new_title: str | None = None
    # 旧档案快照
    old_name: str = ""
    old_phone: str | None = None
    old_title: str | None = None
    old_company: str | None = None


class MergeDecisionRequest(BaseModel):
    decision: str = Field(..., description="approved/rejected")
    remark: str | None = None
