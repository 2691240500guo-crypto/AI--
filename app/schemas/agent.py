"""AI Agent 任务接口模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class AgentTaskOut(ORMModel):
    id: int
    agent_code: str
    result_id: int | None
    input_json: dict[str, Any] | None
    output_json: dict[str, Any] | None
    state_json: dict[str, Any] | None
    status: str
    current_node: str | None
    retry_count: int
    error_msg: str | None
    created_at: datetime
    updated_at: datetime


class AgentTaskListOut(BaseModel):
    items: list[AgentTaskOut]
