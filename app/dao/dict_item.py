"""数据字典 DAO（A11）。"""
from app.dao.base import BaseDAO
from app.models.dict_item import DictItem, DictType


class DictTypeDAO(BaseDAO[DictType]):
    __model__ = DictType


class DictItemDAO(BaseDAO[DictItem]):
    __model__ = DictItem
