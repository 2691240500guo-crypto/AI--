"""岗位匹配域 DAO（M 域）。"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.matching import MatchPushLog, MatchResult, MatchRule, PosPosition


class PosPositionDAO(BaseDAO[PosPosition]):
    __model__ = PosPosition

    @classmethod
    def get_by_code(cls, db: Session, code: str) -> PosPosition | None:
        return cls.get_by(db, code=code)


class MatchRuleDAO(BaseDAO[MatchRule]):
    __model__ = MatchRule

    @classmethod
    def default_rule(cls, db: Session) -> MatchRule | None:
        """取第一条启用规则作为默认匹配规则。"""
        stmt = select(MatchRule).where(MatchRule.status == 1).order_by(MatchRule.id.asc()).limit(1)
        return db.scalar(stmt)


class MatchResultDAO(BaseDAO[MatchResult]):
    __model__ = MatchResult

    @classmethod
    def get_by_pair(cls, db: Session, talent_id: int, position_id: int) -> MatchResult | None:
        return cls.get_by(db, talent_id=talent_id, position_id=position_id)

    @classmethod
    def list_by_position(cls, db: Session, position_id: int, limit: int = 50) -> list[MatchResult]:
        return cls.list(db, MatchResult.position_id == position_id,
                        limit=limit, order_by=MatchResult.score.desc())


class MatchPushLogDAO(BaseDAO[MatchPushLog]):
    __model__ = MatchPushLog
