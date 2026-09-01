"""通用 DAO 基类：继承即得单表增删改查 + 分页，减少重复代码。

用法（新增模块只需继承并标注 model）:
    class TalentDAO(BaseDAO[Talent]):
        __model__ = Talent
"""
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base

T = TypeVar("T", bound=Base)


class BaseDAO(Generic[T]):
    __model__: type[T]

    @classmethod
    def get(cls, db: Session, obj_id: int) -> T | None:
        return db.get(cls.__model__, obj_id)

    @classmethod
    def get_by(cls, db: Session, **kwargs) -> T | None:
        stmt = select(cls.__model__).filter_by(**kwargs)
        return db.scalar(stmt)

    @classmethod
    def list(cls, db: Session, *where, offset: int = 0, limit: int = 100, order_by=None) -> list[T]:
        stmt = select(cls.__model__).where(*where)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        return list(db.scalars(stmt.offset(offset).limit(limit)).all())

    @classmethod
    def create(cls, db: Session, **fields) -> T:
        obj = cls.__model__(**fields)
        db.add(obj)
        db.flush()
        return obj

    @classmethod
    def update(cls, db: Session, obj: T, **fields) -> T:
        for k, v in fields.items():
            if v is not None:
                setattr(obj, k, v)
        db.flush()
        return obj

    @classmethod
    def delete(cls, db: Session, obj: T) -> None:
        db.delete(obj)
        db.flush()