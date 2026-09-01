"""岗位匹配域 Schema（M 域）：请求/响应模型。"""
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class PositionCreate(BaseModel):
    sys_position_id: int | None = None  # 对应基础岗位/职级
    name: str = Field(..., max_length=64, description="岗位名称")
    code: str = Field(..., max_length=64, description="岗位编码(唯一)")
    dept_id: int | None = None  # 所属部门
    headcount: int = Field(0, ge=0, description="编制人数")
    filled: int = Field(0, ge=0, description="已到岗人数")
    status: int = Field(1, description="1启用 0停用")
    description: str | None = None  # 岗位说明书（画像化输入源）


class PositionUpdate(BaseModel):
    sys_position_id: int | None = None
    name: str | None = Field(None, max_length=64)
    code: str | None = Field(None, max_length=64)
    dept_id: int | None = None
    headcount: int | None = Field(None, ge=0)
    filled: int | None = Field(None, ge=0)
    status: int | None = None
    description: str | None = None


class PositionOut(ORMModel):
    id: int
    sys_position_id: int | None
    name: str
    code: str
    dept_id: int | None
    headcount: int
    filled: int
    status: int
    description: str | None
    created_at: datetime
    updated_at: datetime


class VectorOut(BaseModel):
    position_id: int
    vector_dim: int
    text: str
    message: str = "岗位画像向量化成功"


class MatchRuleCreate(BaseModel):
    name: str = Field(..., max_length=64)
    rule_json: dict[str, float] | None = None  # 维度权重 {"skill":0.4,...}
    status: int = 1


class MatchRuleOut(ORMModel):
    id: int
    name: str
    rule_json: str | None
    status: int
    created_at: datetime


class MatchRequest(BaseModel):
    talent_ids: list[int] | None = None  # 为空则检索全部人才
    position_ids: list[int] | None = None  # 为空则匹配全部岗位
    rule_id: int | None = None  # 匹配规则（默认取启用规则第一条）
    top_k: int = Field(10, ge=1, le=100, description="每人/岗召回量")


class MatchResultOut(ORMModel):
    id: int
    talent_id: int
    position_id: int
    score: Decimal
    dimension_json: str | None
    explain: str | None
    rank: int | None
    status: int
    created_at: datetime


class AlertOut(ORMModel):
    id: int
    match_id: int
    type: str  # reserve/vacancy
    target_user: str | None
    message_id: int | None
    created_at: datetime


class MatchTaskOut(BaseModel):
    """匹配任务结果（M-3 输出）。"""
    task: str = "match"
    total: int = 0
    results: list[dict[str, Any]] = []


# ==================== 岗位人才匹配 Agent（M-Agent） ====================


class AgentParseRequest(BaseModel):
    position_id: int = Field(..., ge=1, description="岗位ID")


class AgentRunRequest(BaseModel):
    """岗位→人才匹配请求。"""
    position_id: int = Field(..., ge=1, description="岗位ID")
    top_k: int = Field(10, ge=1, le=100, description="返回候选数")
    min_score: float = Field(0.0, ge=0, le=100, description="最低匹配分过滤")
    gen_explain: bool = Field(True, description="是否生成匹配原因解释")
    # 筛选排序覆盖项（不传则用 Agent 解析的门槛）
    degree_required: str | None = Field(None, description="学历门槛覆盖：博士/硕士/本科/大专")
    years_required: int | None = Field(None, ge=0, description="经验门槛覆盖（年）")
    mandatory_skills: list[str] | None = Field(None, description="必备技能覆盖")


class AgentReverseRequest(BaseModel):
    """人才→岗位反向匹配请求。"""
    talent_id: int = Field(..., ge=1, description="人才ID")
    top_k: int = Field(10, ge=1, le=100, description="返回岗位数")
    min_score: float = Field(0.0, ge=0, le=100, description="最低匹配分过滤")


class AgentChatRequest(BaseModel):
    """自然语言操作请求。"""
    message: str = Field(..., min_length=1, max_length=500, description="自然语言指令")
