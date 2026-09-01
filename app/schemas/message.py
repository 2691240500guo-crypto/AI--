from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import ORMModel


class MessageSend(BaseModel):
    type_code: str = "system"
    title: str
    content: str = ""
    receiver_ids: list[int] = []   # 空=全员
    biz_type: str | None = None
    biz_id: int | None = None
    push_miniapp: int = 0


class MessageOut(ORMModel):
    id: int
    type_code: str
    title: str
    content: str
    sender_id: int | None
    biz_type: str | None
    biz_id: int | None
    push_miniapp: int = 0  # 推送状态：0 未推，1 已推（H5 补推后置 1）
    status: int
    created_at: datetime
    # 面向当前接收人
    is_read: bool = False
