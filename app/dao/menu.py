"""菜单 DAO。"""
from app.dao.base import BaseDAO
from app.models.menu import Menu


class MenuDAO(BaseDAO[Menu]):
    __model__ = Menu