"""人才去重审核 DAO（批次 C）。"""
# hq新增内容 - 人才档案批次C
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.talent_merge import TalentMerge


class TalentMergeDAO(BaseDAO[TalentMerge]):
    __model__ = TalentMerge

    @classmethod
    def list_pending(cls, db: Session, limit: int = 100) -> list[TalentMerge]:
        """待审核队列（按时间倒序）。"""
        stmt = (
            select(TalentMerge)
            .where(TalentMerge.status == "pending")
            .order_by(TalentMerge.id.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def find_open_for_new(cls, db: Session, new_talent_id: int) -> list[TalentMerge]:
        """某新档案尚未处理的审核记录（防止重复建单）。"""
        stmt = (
            select(TalentMerge)
            .where(TalentMerge.new_talent_id == new_talent_id,
                   TalentMerge.status == "pending")
        )
        return list(db.scalars(stmt).all())
