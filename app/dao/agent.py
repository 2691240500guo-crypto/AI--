"""AI Agent 任务数据访问层。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.agent import AgentTask


class AgentTaskDAO(BaseDAO[AgentTask]):
    __model__ = AgentTask

    @classmethod
    def list_by_result(cls, db: Session, result_id: int) -> list[AgentTask]:
        statement = select(cls.__model__).where(
            cls.__model__.result_id == result_id
        ).order_by(cls.__model__.id.desc())
        return list(db.scalars(statement).all())
