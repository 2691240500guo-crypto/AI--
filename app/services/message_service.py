"""消息服务（H01-H04）：业务层统一入口，其他模块只需调用 notify() 即可推送。"""
from sqlalchemy import func, or_, select  # 导入聚合函数、OR 条件与查询构造器
from sqlalchemy.orm import Session  # 导入数据库会话类型

from app.dao.base import BaseDAO  # 导入通用 DAO 基类
from app.dao.message import MessageDAO, csv_contains  # 导入消息数据访问层与精确 CSV 匹配
from app.models.message import Message  # 导入消息 ORM 模型
from app.models.user import User  # 导入用户 ORM 模型
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
        """发一条消息；receiver_ids 为空表示全员，非空值必须是 sys_user.id。"""
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
        """业务自动推送入口；receiver_ids 契约统一使用 sys_user.id。"""
        final_title = title or type_code  # 未传标题时用消息类型编码兜底
        return cls.send(db, type_code=type_code, title=final_title, content=content,  # 复用发送逻辑落库
                        sender_id=sender_id, receiver_ids=receiver_ids,  # 传入发送人与接收人
                        biz_type=biz_type, biz_id=biz_id,  # 传入业务关联信息
                        push_miniapp=push_miniapp)  # 传入 H5 推送标记

    @staticmethod
    def _visible_filter(user_id: int):
        """构造消息可见条件：全员消息或接收人 CSV 中存在完整 user_id。"""
        return or_(Message.receiver_ids == "0", csv_contains(Message.receiver_ids, user_id))

    @staticmethod
    def _unread_filter(user_id: int):
        """构造未读条件，避免 read_ids 中的子串造成误判。"""
        return or_(
            Message.read_ids.is_(None),
            Message.read_ids == "",
            ~csv_contains(Message.read_ids, user_id),
        )

    @staticmethod
    def user_id_for_talent(db: Session, talent_id: int) -> int | None:
        """将人才档案 ID 映射为消息契约要求的 sys_user.id。"""
        return db.scalar(select(User.id).where(User.talent_id == talent_id, User.status == 1))

    @staticmethod
    def hr_user_ids(db: Session) -> list[int]:
        """返回管理端用户 ID，避免 HR 预警进入员工消息中心。"""
        stmt = select(User.id).where(
            User.status == 1,
            User.talent_id.is_(None),
            or_(User.user_type != "employee", User.user_type.is_(None)),
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def for_user(cls, db: Session, user_id: int, page: int = 1, page_size: int = 20,
                 unread_only: bool = False) -> tuple[list[Message], int]:
        """查询当前用户的消息列表，返回行列表与总数。"""
        base = cls._visible_filter(user_id)  # 全员消息或发给本人
        conditions = [base]
        if unread_only:  # 只看未读时
            conditions.append(cls._unread_filter(user_id))  # 过滤掉已读消息
        total = db.scalar(select(func.count()).select_from(Message).where(*conditions)) or 0  # 统计当前筛选总数
        stmt = select(Message).where(*conditions).order_by(Message.id.desc())  # 构造按 id 倒序的查询
        rows = list(db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all())  # 分页取行
        return rows, total  # 返回列表与总数

    @classmethod
    def unread_count(cls, db: Session, user_id: int) -> int:
        """查询当前用户全部可见消息中的未读数量。"""
        return db.scalar(
            select(func.count()).select_from(Message).where(
                cls._visible_filter(user_id), cls._unread_filter(user_id)
            )
        ) or 0

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
        base = cls._visible_filter(user_id)  # 全员消息或发给本人
        stmt = select(Message).where(base, cls._unread_filter(user_id))  # 过滤出当前用户未读消息
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
