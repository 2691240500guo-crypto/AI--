"""人才 AI 解析报告（批次 2.3b）。

LLM 抽出的非标量结果（skills / highlights / 评估总结等）单独建表，
避免 ``biz_talent`` 主档字段膨胀。
- ``parsed_json``: 完整抽取结果（重跑时覆盖）
- ``summary_report``: 评估总结（亮点 / 短板 / 适配 / 潜力四段）
- ``vector_id``: Milvus 主向量 id（2.3c 写入）

仅本模块新增。
"""
# hq新增内容 - 人才档案批次2.3b
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TalentReport(Base):
    """人才 AI 解析报告。"""

    __tablename__ = "tal_talent_report"
    __table_args__ = (
        # hq+  一个 talent 只会保留最新一份报告（重跑覆盖），用 unique 简化查询
        #     但需要 server-side 处理 upsert
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(
        ForeignKey("tal_talent.id", ondelete="CASCADE"),
        unique=True, index=True,
    )

    # 完整抽取 JSON（用于前端调试 / 重跑 diff）
    parsed_json: Mapped[str | None] = mapped_column(Text, default=None)
    # 拆分字段，便于列表展示 / 检索过滤
    skills: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON list")
    highlights: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON list")
    shortcomings: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON list")
    fit_positions: Mapped[str | None] = mapped_column(Text, default=None, comment="JSON list")
    potential: Mapped[str | None] = mapped_column(String(16), default=None, comment="P5/P6/P7")
    # 袁文武 2026-09-02：AI 解析新增三大板块
    ability_level: Mapped[str | None] = mapped_column(String(32), default=None, comment="能力等级，如 P5初级/P6中级/P7高级/P8专家")
    experience_summary: Mapped[str | None] = mapped_column(Text, default=None, comment="从业经验总结（2-3 句）")
    composite_score: Mapped[int | None] = mapped_column(default=None, comment="综合评分 0-100")
    # 评估总结（自然语言一段）
    summary_report: Mapped[str | None] = mapped_column(Text, default=None)

    # 2.3c 用：Milvus 主向量 id
    vector_id: Mapped[str | None] = mapped_column(String(64), default=None)

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)
