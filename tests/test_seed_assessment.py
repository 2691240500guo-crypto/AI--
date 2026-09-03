"""C assessment seed data must match the split talent/user identity schema."""

from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register every FK target in Base.metadata
from app.db.base import Base
from app.db.seed_assessment import reset_assessment_demo_data, seed_assessment
from app.models.assessment import (
    AssessmentBatch,
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentResult,
    QuestionBank,
)
from app.models.dept import Dept
from app.models.talent import Talent
from app.models.user import User


def _session() -> tuple[sa.Engine, Session]:
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    db = factory()
    db.add(Dept(id=1, name="总部", parent_id=0, sort=1, status=1))
    db.commit()
    return engine, db


def _counts(db: Session) -> dict[str, int]:
    models = (User, Talent, QuestionBank, AssessmentQuestion, AssessmentPaper, AssessmentBatch, AssessmentResult)
    return {
        model.__tablename__: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for model in models
    }


def _assert_result_identities(db: Session) -> list[AssessmentResult]:
    results = list(db.scalars(select(AssessmentResult).order_by(AssessmentResult.id)).all())
    assert results
    for result in results:
        user = db.get(User, result.user_id)
        assert user is not None
        assert user.talent_id == result.talent_id
        assert db.get(Talent, result.talent_id) is not None
    return results


def test_seed_is_idempotent_and_reset_rebuilds_with_both_identity_columns():
    engine, db = _session()
    try:
        seed_assessment(db)
        first_counts = _counts(db)
        results = _assert_result_identities(db)

        seed_assessment(db)
        assert _counts(db) == first_counts
        _assert_result_identities(db)

        results[0].score = Decimal("999.00")
        db.commit()
        deleted = reset_assessment_demo_data(db)

        assert deleted["results"] == first_counts["asm_result"]
        assert _counts(db) == first_counts
        rebuilt = _assert_result_identities(db)
        assert all(result.score != Decimal("999.00") for result in rebuilt)
    finally:
        db.close()
        engine.dispose()
