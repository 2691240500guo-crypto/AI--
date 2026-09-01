"""数据字典服务（A11）：业务枚举走字典，改配置不改代码。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.dict_item import DictItem


class DictService:
    @staticmethod
    def items(db: Session, type_code: str) -> list[DictItem]:
        stmt = select(DictItem).where(
            DictItem.type_code == type_code, DictItem.status == 1).order_by(DictItem.sort)
        return list(db.scalars(stmt).all())