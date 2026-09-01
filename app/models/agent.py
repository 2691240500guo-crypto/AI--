"""AI Agent 任务状态模型。"""

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentTask(Base):
    __tablename__ = "ai_agent_task"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_code: Mapped[str] = mapped_column(String(32), index=True)
    result_id: Mapped[int | None] = mapped_column(
        ForeignKey("asm_result.id", ondelete="SET NULL"), default=None, index=True
    )
    input_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    output_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    state_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    current_node: Mapped[str | None] = mapped_column(String(64), default=None)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_msg: Mapped[str | None] = mapped_column(String(1000), default=None)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, index=True)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.now, onupdate=datetime.now)

    result = relationship("AssessmentResult", back_populates="agent_tasks")
