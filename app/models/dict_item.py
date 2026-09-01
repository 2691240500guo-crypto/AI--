from datetime import datetime
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DictType(Base):
    """数据字典类型（A11）。"""
    __tablename__ = "sys_dict_type"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    remark: Mapped[str | None] = mapped_column(String(255), default=None)
    status: Mapped[int] = mapped_column(default=1)


class DictItem(Base):
    """数据字典项。业务枚举走字典，改配置不改代码。"""
    __tablename__ = "sys_dict_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type_code: Mapped[str] = mapped_column(String(32), index=True)
    label: Mapped[str] = mapped_column(String(64))   # 显示名
    value: Mapped[str] = mapped_column(String(64))   # 存储值
    sort: Mapped[int] = mapped_column(default=0)
    status: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)