"""岗位匹配域模型（M 域）：业务岗位 / 匹配规则 / 匹配结果 / 推送预警日志。

说明：
- pos_position.sys_position_id -> sys_position.id（S 域基础岗位，已存在）
- pos_position.dept_id        -> sys_dept.id（S 域部门，已存在）
- match_result.talent_id      -> 关联 tal_talent.id，但人才档案域表未建且不在本域职责内，
                                 故此处只建普通索引列，不加外键约束（避免建表失败）。
- match_result.position_id    -> pos_position.id（本域）
- match_push_log.match_id     -> match_result.id（本域）
- match_push_log.message_id   -> msg_center.id（消息中心，已存在，可空）
"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PosPosition(Base):
    """业务岗位（M-1 岗位管理）。"""

    __tablename__ = "pos_position"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sys_position_id: Mapped[int | None] = mapped_column(
        ForeignKey("sys_position.id"), default=None
    )  # 对应基础岗位/职级（可空）
    name: Mapped[str] = mapped_column(String(64), index=True)  # 岗位名称
    code: Mapped[str] = mapped_column(String(64), unique=True)  # 岗位编码（UK）
    dept_id: Mapped[int | None] = mapped_column(
        ForeignKey("sys_dept.id"), default=None
    )  # 所属部门（可空）
    headcount: Mapped[int] = mapped_column(default=0)  # 编制人数
    filled: Mapped[int] = mapped_column(default=0)  # 已到岗人数
    status: Mapped[int] = mapped_column(default=1)  # 1启用 0停用
    description: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # 岗位说明书（画像化输入源）
    parsed_json: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # 岗位智能解析结果 JSON（需求1 标签体系持久化）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now
    )


class MatchRule(Base):
    """匹配规则（维度权重配置）。"""

    __tablename__ = "match_rule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))  # 规则名称
    rule_json: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # 维度权重 JSON，如 {"skill":0.4,"degree":0.2,"years":0.2,"quality":0.2}
    status: Mapped[int] = mapped_column(default=1)  # 1启用 0停用
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class MatchResult(Base):
    """匹配结果（M-3 输出）。"""

    __tablename__ = "match_result"
    __table_args__ = (UniqueConstraint("talent_id", "position_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    talent_id: Mapped[int] = mapped_column(index=True)  # 人才ID（关联 tal_talent，见模块说明）
    position_id: Mapped[int] = mapped_column(
        ForeignKey("pos_position.id"), index=True
    )
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)  # 匹配度 0-100
    dimension_json: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # 各维度得分 JSON
    explain: Mapped[str | None] = mapped_column(
        Text, default=None
    )  # 解释依据（Agent③ 生成）
    rank: Mapped[int | None] = mapped_column(default=None)  # 排序名次
    status: Mapped[int] = mapped_column(default=0)  # 0候选 1推荐 2录用
    warm_level: Mapped[int] = mapped_column(default=0)  # 储备保温等级 0无 1低 2中 3高（需求4）
    last_follow_up: Mapped[datetime | None] = mapped_column(
        default=None
    )  # 最近跟进时间（保温管理，需求4）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)


class MatchPushLog(Base):
    """储备/空缺预警推送日志（M-5）。"""

    __tablename__ = "match_push_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("match_result.id"), index=True
    )
    type: Mapped[str] = mapped_column(String(16))  # 储备 reserve / 空缺 vacancy
    target_user: Mapped[str | None] = mapped_column(
        String(64), default=None
    )  # 目标用户（用户名/ID）
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("msg_center.id"), default=None
    )  # 关联消息（可空）
    created_at: Mapped[datetime] = mapped_column(default=datetime.now)
