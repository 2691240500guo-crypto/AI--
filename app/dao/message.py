"""消息 DAO（H01-H04）：负责消息表的数据访问。"""
from sqlalchemy import select  # 导入查询构造器
from sqlalchemy.orm import Session  # 导入数据库会话类型

from app.dao.base import BaseDAO  # 导入通用 DAO 基类
from app.models.message import Message  # 导入消息 ORM 模型


class MessageDAO(BaseDAO[Message]):
    """消息表数据访问类，继承通用增删改查能力。"""
    __model__ = Message  # 绑定当前 DAO 操作的消息模型

    @classmethod
    def get_visible_message(cls, db: Session, message_id: int, user_id: int) -> Message | None:
        """查询当前用户可见的消息：本人接收或全员消息，不可见返回 None。"""
        uid = str(user_id)  # 把当前用户 id 转成字符串
        stmt = select(Message).where(  # 构造按可见范围过滤的查询
            Message.id == message_id,  # 限定消息 id
            (Message.receiver_ids == "0") | (Message.receiver_ids.contains(uid)),  # 全员消息或包含当前用户
        )
        return db.scalars(stmt).first()  # 返回第一条结果，没有则返回 None
