"""标签字典 DAO（批次 2.1）。"""
# hq新增内容 - 人才档案批次2.1
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.talent_dict import TalentDict


class TalentDictDAO(BaseDAO[TalentDict]):
    __model__ = TalentDict

    @classmethod
    def list_filtered(cls, db: Session, type: str | None = None,
                      keyword: str | None = None, only_enabled: bool = True) -> list[TalentDict]:
        stmt = select(TalentDict)
        if only_enabled:
            stmt = stmt.where(TalentDict.enabled == 1)
        if type:
            stmt = stmt.where(TalentDict.type == type)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where((TalentDict.code.like(like)) | (TalentDict.name.like(like)))
        stmt = stmt.order_by(TalentDict.type, TalentDict.sort, TalentDict.id)
        return list(db.scalars(stmt).all())

    @classmethod
    def get_by_code(cls, db: Session, code: str) -> TalentDict | None:
        return db.scalar(select(TalentDict).where(TalentDict.code == code))
