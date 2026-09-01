"""消息服务（H01-H04）：业务层统一入口，其他模块只需调用 notify() 即可推送。"""
from sqlalchemy import func, select  # 导入聚合函数与查询构造器
from sqlalchemy.orm import Session  # 导入数据库会话类型

from app.dao.base import BaseDAO  # 导入通用 DAO 基类
from app.dao.message import MessageDAO  # 导入消息数据访问层
from app.models.message import Message  # 导入消息 ORM 模型
from app.utils.logger import logger  # 导入统一日志


class MessageService:
    """消息业务服务类。"""
    __model__ = Message  # 绑定消息模型

    @classmethod
    def get_detail(cls, db: Session, message_id: int, user_id: int) -> Message | None:
        """按当前用户可见范围查询消息详情，不可见返回 None。"""
        return MessageDAO.get_visible_message(db, message_id, user_id)  # 复用 DAO 的可见性查询

    @classmethod
    def send(cls, db: Session, *, type_code: str, title: str, content: str = "",
             sender_id: int | None = None, receiver_ids: list[int] | None = None,
             biz_type: str | None = None, biz_id: int | None = None,
             push_miniapp: int = 0) -> Message:
        """发一条消息；receiver_ids 为空表示全员。"""
        msg = Message(  # 构造消息对象
            type_code=type_code,  # 消息类型编码
            title=title,  # 消息标题
            content=content,  # 消息内容
            sender_id=sender_id,  # 发送人 id
            receiver_ids=",".join(map(str, receiver_ids)) if receiver_ids else "0",  # 接收人逗号串，空为全员
            biz_type=biz_type,  # 关联业务类型
            biz_id=biz_id,  # 关联业务主键
            push_miniapp=push_miniapp,  # 是否触发 H5 推送
        )
        db.add(msg)  # 把消息加入数据库会话
        db.flush()  # 立即落库以便获取消息 id
        # H04：若要求推送，此处接入 H5 提醒逻辑
        if push_miniapp:  # 需要推送时
            cls._push_miniapp(msg)  # 调用推送占位逻辑
        return msg  # 返回新消息对象

    @classmethod
    def notify(cls, db: Session, type_code: str, receiver_ids: list[int], content: str, *,
               title: str | None = None, sender_id: int | None = None,
               biz_type: str | None = None, biz_id: int | None = None,
               push_miniapp: int = 0) -> Message:
        """业务自动推送入口，契约支持 notify("training", [talent_id], "内容")。"""
        final_title = title or type_code  # 未传标题时用消息类型编码兜底
        return cls.send(db, type_code=type_code, title=final_title, content=content,  # 复用发送逻辑落库
                        sender_id=sender_id, receiver_ids=receiver_ids,  # 传入发送人与接收人
                        biz_type=biz_type, biz_id=biz_id,  # 传入业务关联信息
                        push_miniapp=push_miniapp)  # 传入 H5 推送标记

    @classmethod
    def for_user(cls, db: Session, user_id: int, page: int = 1, page_size: int = 20,
                 unread_only: bool = False) -> tuple[list[Message], int]:
        """查询当前用户的消息列表，返回行列表与总数。"""
        uid = str(user_id)  # 把用户 id 转成字符串
        base = (Message.receiver_ids == "0") | (Message.receiver_ids.contains(uid))  # 全员消息或发给本人
        total = db.scalar(select(func.count()).select_from(Message).where(base)) or 0  # 统计消息总数
        stmt = select(Message).where(base).order_by(Message.id.desc())  # 构造按 id 倒序的查询
        if unread_only:  # 只看未读时
            stmt = stmt.where(~Message.read_ids.contains(uid))  # 过滤掉已读消息
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())  # 分页取行
        return rows, total  # 返回列表与总数

    @classmethod
    def mark_read(cls, db: Session, msg: Message, user_id: int) -> None:
        """把当前用户标记为已读。"""
        uid = str(user_id)  # 把用户 id 转成字符串
        if uid not in [s for s in (msg.read_ids or "").split(",") if s]:  # 未读过才处理
            msg.read_ids = ",".join(filter(bool, [msg.read_ids, uid]))  # 把当前用户追加到已读串
            db.flush()  # 立即保存修改

    @classmethod
    def read_all(cls, db: Session, user_id: int) -> int:
        """把当前用户所有未读消息标记为已读，返回处理条数。"""
        uid = str(user_id)  # 把用户 id 转成字符串
        base = (Message.receiver_ids == "0") | (Message.receiver_ids.contains(uid))  # 全员消息或发给本人
        stmt = select(Message).where(base, ~Message.read_ids.contains(uid))  # 过滤出当前用户未读消息
        rows = list(db.scalars(stmt).all())  # 取出全部未读消息
        for m in rows:  # 逐条标记
            m.read_ids = ",".join(filter(bool, [m.read_ids, uid]))  # 把当前用户追加到已读串
        db.flush()  # 批量保存修改
        return len(rows)  # 返回处理条数

    @classmethod
    def push_reminder(cls, db: Session, msg: Message) -> bool:
        """手动触发一次 H5 补推提醒，已推送过返回 False。"""
        if msg.push_miniapp == 1:  # 已标记推送过
            return False  # 幂等返回，不重复推送
        msg.push_miniapp = 1  # 标记为已推送
        cls._push_miniapp(msg)  # 调用 H5 推送占位逻辑
        db.flush()  # 保存推送标记
        return True  # 返回本次执行了推送

    @staticmethod
    def _push_miniapp(msg: Message) -> None:
        """H5 推送占位逻辑：本期写日志，后续接真实提醒通道。"""
        logger.info("H5 推送占位：消息 id=%s", msg.id)  # 记录推送占位日志


def notify(db: Session, type_code: str, receiver_ids: list[int], content: str, **kwargs) -> Message:
    """模块级一行推送入口，等价 MessageService.notify()。"""
    return MessageService.notify(db, type_code, receiver_ids, content, **kwargs)  # 委托给服务类方法
