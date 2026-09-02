"""消息路由（H01-H04）：对外接口层，只做参数绑定与鉴权，业务逻辑交给 service。"""
from fastapi import APIRouter, Depends, HTTPException, Query  # 导入路由与依赖组件
from sqlalchemy.orm import Session  # 导入数据库会话类型

from app.core.deps import get_current_user, require_client  # 导入当前用户鉴权依赖
from app.db.session import get_db  # 导入数据库会话依赖
from app.dao.message import MessageDAO  # 导入消息数据访问层
from app.models.message import Message  # 导入消息 ORM 模型
from app.models.user import User  # 导入用户 ORM 模型
from app.schemas.message import MessageOut, MessageSend  # 导入消息出入参 DTO
from app.services.message_service import MessageService  # 导入消息业务服务
from app.utils.pagination import paged_result  # 导入分页响应工具
from app.utils.response import ok  # 导入统一成功响应

router = APIRouter()  # 创建消息路由对象

# 端策略：读"我的消息"两端均可（管理端员工端都看自己的）；send/push-miniapp 为管理端写操作
_READ_CLIENT = require_client(["admin", "app"])


def _out(msg: Message, user_id: int) -> MessageOut:
    """把消息模型转成输出 DTO，并计算当前用户是否已读。"""
    o = MessageOut.model_validate(msg)  # 转换消息基础字段
    o.is_read = str(user_id) in [s for s in (msg.read_ids or "").split(",") if s]  # 判断当前用户是否已读
    return o  # 返回输出对象


@router.get("", summary="查询我的消息列表", dependencies=[Depends(_READ_CLIENT)])
def my_messages(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                unread_only: bool = False, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    """查询当前用户的消息列表，支持分页与只看未读。"""
    rows, total = MessageService.for_user(db, user.id, page, page_size, unread_only)  # 调用业务层查询
    return ok(paged_result([_out(m, user.id) for m in rows], page, page_size, total))  # 返回分页结果


@router.post("/send", summary="发送消息（管理端）", dependencies=[Depends(require_client("admin"))])
def send(body: MessageSend, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """发送消息，按需求文档路径 POST /messages/send，也作为其他模块 notify 的入口。"""
    msg = MessageService.send(db, type_code=body.type_code, title=body.title,  # 调用发送逻辑
                              content=body.content, sender_id=user.id,  # 传入内容与发送人
                              receiver_ids=body.receiver_ids, biz_type=body.biz_type,  # 接收人与业务类型
                              biz_id=body.biz_id, push_miniapp=body.push_miniapp)  # 业务 id 与推送标记
    db.commit()  # 提交事务
    return ok(MessageOut.model_validate(msg))  # 返回新消息


@router.post("/{mid}/read", summary="标记消息已读", dependencies=[Depends(_READ_CLIENT)])
def mark_read(mid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """把指定消息标记为当前用户已读。"""
    m = MessageService.get_detail(db, mid, user.id)  # 只允许当前用户可见的消息被标记已读
    if not m:  # 消息不存在时
        raise HTTPException(404, "消息不存在")  # 返回 404
    MessageService.mark_read(db, m, user.id)  # 调用业务层标记已读
    db.commit()  # 提交事务
    return ok({})  # 返回成功响应


@router.get("/unread-count", summary="查询未读消息数", dependencies=[Depends(_READ_CLIENT)])
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """查询当前用户未读消息数量。"""
    return ok({"unread": MessageService.unread_count(db, user.id)})  # 统计全部可见消息


@router.post("/read-all", summary="全部消息标记已读", dependencies=[Depends(_READ_CLIENT)])
def read_all(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按需求 9.3 把当前用户所有未读消息标记为已读。"""
    count = MessageService.read_all(db, user.id)  # 调用业务层批量标记已读
    db.commit()  # 提交事务
    return ok({"updated": count})  # 返回已处理条数


@router.post("/{mid}/push-miniapp", summary="手动补推提醒（管理端）", dependencies=[Depends(require_client("admin"))])
def push_miniapp(mid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按需求 H04 手动触发 H5 补推提醒，已推送过则幂等返回。"""
    m = MessageDAO.get(db, mid)  # 按 id 查询消息
    if not m:  # 消息不存在时
        raise HTTPException(404, "消息不存在")  # 返回 404
    pushed = MessageService.push_reminder(db, m)  # 调用补推逻辑
    db.commit()  # 提交事务
    return ok({"pushed": pushed})  # 返回本次是否执行推送


@router.get("/{mid}", summary="查询消息详情", dependencies=[Depends(_READ_CLIENT)])
def message_detail(mid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按需求 9.3 提供消息详情，仅接收人本人或全员消息可见。"""
    msg = MessageService.get_detail(db, mid, user.id)  # 按当前用户可见范围取消息
    if not msg:  # 不可见或不存在时
        raise HTTPException(404, "消息不存在")  # 统一返回 404，避免泄露消息是否存在
    return ok(_out(msg, user.id))  # 返回消息详情并带 is_read
