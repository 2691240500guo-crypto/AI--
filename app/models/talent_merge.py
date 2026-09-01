"""人才去重审核记录（批次 C）。

场景：
- 上传简历 LLM 抽取后，用 name / phone 与库内已有档案比对：
    - 姓名 + 电话 都匹配（double）→ 前端弹确认，用户确认后调用 merge-overwrite 覆盖旧档案
    - 仅姓名 或 仅电话 匹配（name/phone）→ 进入人工审核队列（pending），
      审核人批准后覆盖，驳回则保留新档案正常新增
- ``status``: pending=待审核 / approved=已确认合并 / rejected=驳回不合并
- 合并动作：merge-overwrite 会用新档案字段覆盖旧档案，软删新档案，并重打标签+重算向量

仅本模块新增。
"""
# hq新增内容 - 人才档案批次C
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TalentMerge(Base):
    """人才去重审核记录。"""

    __tablename__ = "tal_talent_merge"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 新档案（本次上传的）与疑似重复的旧档案
    new_talent_id: Mapped[int] = mapped_column(
        ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True,
        comment="新上传人才 id",
    )
    old_talent_id: Mapped[int] = mapped_column(
        ForeignKey("tal_talent.id", ondelete="CASCADE"), index=True,
        comment="疑似重复的旧人才 id",
    )

    # 匹配类型：double=姓名+电话 / name=仅姓名 / phone=仅电话
    match_type: Mapped[str] = mapped_column(String(16), default="name",
                                            comment="double/name/phone")
    status: Mapped[str] = mapped_column(String(16), default="pending",
                                        comment="pending/approved/rejected")
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment="审核备注/处理说明")

    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    def __repr__(self) -> str:  # noqa: D401
        return f"<TalentMerge {self.new_talent_id}~{self.old_talent_id} {self.match_type} {self.status}>"
