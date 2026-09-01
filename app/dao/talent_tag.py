"""人才 ↔ 标签 关联 DAO（批次 2.1）。"""
# hq新增内容 - 人才档案批次2.1
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.talent_dict import TalentDict
from app.models.talent_tag import TalentTag


class TalentTagDAO(BaseDAO[TalentTag]):
    __model__ = TalentTag

    @classmethod
    def list_for_talent(cls, db: Session, talent_id: int) -> list[TalentTag]:
        """取某人才的全部标签（同时把字典一起返回，便于出参展示）。"""
        stmt = (
            select(TalentTag, TalentDict)
            .join(TalentDict, TalentTag.dict_id == TalentDict.id)
            .where(TalentTag.talent_id == talent_id)
            .order_by(TalentDict.type, TalentDict.sort)
        )
        # 返回 (TalentTag, TalentDict) 元组列表，service 层负责拍平
        return list(db.execute(stmt).all())

    @classmethod
    def replace_for_talent(cls, db: Session, talent_id: int,
                            dict_ids: list[int], source: str = "manual") -> None:
        """覆盖式绑定：先清空再用新集合写入。source/manual/auto/ai。"""
        db.execute(delete(TalentTag).where(TalentTag.talent_id == talent_id))
        db.flush()
        for did in dict_ids:
            db.add(TalentTag(talent_id=talent_id, dict_id=did, source=source))
        db.flush()

    @classmethod
    def list_for_talents(cls, db: Session, talent_ids: list[int]) -> dict[int, list[tuple[TalentTag, TalentDict]]]:
        """批量取多个人才的标签，返回 {talent_id: [(TalentTag, TalentDict), ...]}。

        与 ``list_for_talent`` 保持一致的元组结构，service 层统一按 (tag, dict) 解包。
        """
        if not talent_ids:
            return {}
        stmt = (
            select(TalentTag, TalentDict)
            .join(TalentDict, TalentTag.dict_id == TalentDict.id)
            .where(TalentTag.talent_id.in_(talent_ids))
            .order_by(TalentDict.type, TalentDict.sort)
        )
        result: dict[int, list[tuple[TalentTag, TalentDict]]] = {tid: [] for tid in talent_ids}
        for tag, d in db.execute(stmt).all():
            result[tag.talent_id].append((tag, d))
        return result
