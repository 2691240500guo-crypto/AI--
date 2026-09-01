"""消息 DAO（H01-H04）。"""
from app.dao.base import BaseDAO
from app.models.message import Message


class MessageDAO(BaseDAO[Message]):
    __model__ = Message
