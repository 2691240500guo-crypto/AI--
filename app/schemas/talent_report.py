"""报告 schema（批次 2.3b）。"""
# hq新增内容 - 人才档案批次2.3b
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TalentReportOut(ORMModel):
    id: int
    talent_id: int
    # hq+  修复：列表类字段允许 None（SQLAlchemy 新建空行 + upsert 只写部分字段时
    #      数据库值是 NULL），Pydantic 默认 list[str] 会因 None 校验失败 422。
    #      改用 Any + model_validator，把 None / 字符串(JSON) / list 都归一为 list。
    skills: Any = []
    highlights: Any = []
    shortcomings: Any = []
    fit_positions: Any = []
    potential: str | None = None
    # 袁文武 2026-09-02：AI 解析新增三大板块
    ability_level: str | None = None
    experience_summary: str | None = None
    composite_score: int | None = None
    summary_report: str | None = None
    vector_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def model_validate(cls, obj, *args, **kwargs):  # noqa: D401
        """宽容模式：把存储为 JSON 字符串的字段反序列化，None 视为 []。"""
        # 允许 dict / model 输入
        try:
            inst = super().model_validate(obj, *args, **kwargs)
        except Exception:
            raise
        for k in ("skills", "highlights", "shortcomings", "fit_positions"):
            v = getattr(inst, k, None)
            if v is None:
                setattr(inst, k, [])
            elif isinstance(v, str):
                import json as _json
                try:
                    parsed = _json.loads(v)
                    setattr(inst, k, parsed if isinstance(parsed, list) else [])
                except Exception:
                    setattr(inst, k, [])
            elif not isinstance(v, list):
                setattr(inst, k, [])
        return inst


class TalentReparseRequest(BaseModel):
    """重跑 AI 解析的请求（可空，等价于用现有 raw_text）。"""
    force: bool = Field(False, description="true 时无视现有 report 直接覆盖")


class TalentReparseResult(BaseModel):
    talent_id: int
    report: TalentReportOut
    new_tag_count: int = Field(0, description="本次 AI 打标签命中的条数")
