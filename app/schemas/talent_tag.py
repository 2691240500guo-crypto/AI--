"""标签 schema（批次 2.1）。

含：
- ``TalentDictCreate/Update/Out``: 字典 CRUD
- ``TalentTagOut``: 关联出参（含字典快照）
- ``TalentTagBind``: 给人才挂/取消标签

仅本模块新增。
"""
# hq新增内容 - 人才档案批次2.1
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ============ TalentDict（字典） ============
class TalentDictCreate(BaseModel):
    code: str = Field(min_length=1, max_length=64, description="标签编码，唯一")
    name: str = Field(min_length=1, max_length=64)
    type: str = Field(description="skill/experience/quality/fit/potential")
    sort: int = 0


class TalentDictUpdate(BaseModel):
    name: str | None = Field(None, max_length=64)
    type: str | None = None
    sort: int | None = None
    enabled: int | None = None


class TalentDictOut(ORMModel):
    id: int
    code: str
    name: str
    type: str
    sort: int
    enabled: int
    created_at: datetime
    # hq+  批次A：标签绑定统计（前端「绑定人才」列用）
    talent_count: int = 0
    talent_names: list[str] = Field(default_factory=list, description="绑定该标签的人才姓名（前 20 个）")


# ============ TalentTag（关联） ============
class TalentTagOut(ORMModel):
    """人才 ↔ 标签关联出参。"""

    id: int
    talent_id: int
    dict_id: int
    source: str
    weight: float
    # 关联字典快照（前端标签 chip 直接用 name/type）
    dict_code: str | None = None
    dict_name: str | None = None
    dict_type: str | None = None


class TalentTagBind(BaseModel):
    """给人才挂标签的入参（批量覆盖式）。"""

    tag_ids: list[int] = Field(default_factory=list, description="要绑定的标签字典 id")
    source: str = Field("manual", description="manual/auto/ai")
