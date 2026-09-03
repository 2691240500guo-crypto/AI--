from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.dao.training import PlanDAO
from app.models.message import Message
from app.routers import training as training_router
from app.routers.training import create_plan, push_plan
from app.services.message_service import MessageService
from app.services.training_agent import TrainingAgentService
from app.services.training_service import PlanService
from app.utils.response import BusinessError


@pytest.fixture
def message_db():
    engine = create_engine("sqlite:///:memory:")
    Message.__table__.create(engine)
    with Session(engine) as db:
        yield db
    engine.dispose()


def _send(db: Session, receiver_ids: list[int] | None, title: str) -> Message:
    message = MessageService.send(
        db,
        type_code="system",
        title=title,
        receiver_ids=receiver_ids,
    )
    db.commit()
    return message


def test_visibility_uses_exact_user_id_and_keeps_broadcasts(message_db: Session):
    direct_40 = _send(message_db, [40], "for 40")
    direct_240 = _send(message_db, [240], "for 240")
    broadcast = _send(message_db, None, "broadcast")

    rows_40, total_40 = MessageService.for_user(message_db, 40)
    rows_41, total_41 = MessageService.for_user(message_db, 41)

    assert {row.id for row in rows_40} == {direct_40.id, broadcast.id}
    assert total_40 == 2
    assert {row.id for row in rows_41} == {broadcast.id}
    assert total_41 == 1
    assert MessageService.get_detail(message_db, direct_240.id, 40) is None
    assert MessageService.get_detail(message_db, broadcast.id, 40) is not None


def test_unread_and_mark_read_use_exact_csv_boundaries(message_db: Session):
    direct_40 = _send(message_db, [40], "for 40")
    _send(message_db, [240], "for 240")
    _send(message_db, None, "broadcast")

    assert MessageService.unread_count(message_db, 40) == 2
    MessageService.mark_read(message_db, direct_40, 40)
    message_db.commit()
    assert MessageService.unread_count(message_db, 40) == 1


def test_training_agent_maps_talent_id_to_user_id(monkeypatch):
    sent = {}
    monkeypatch.setattr(
        PlanService,
        "create",
        staticmethod(lambda *_args, **_kwargs: SimpleNamespace(id=88)),
    )
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, talent_id: 40 if talent_id == 5 else None),
    )

    def fake_send(_db, **kwargs):
        sent.update(kwargs)
        return SimpleNamespace(id=99)

    monkeypatch.setattr(MessageService, "send", staticmethod(fake_send))

    result = TrainingAgentService.generate_plan(
        MagicMock(), talent_id=5, course_ids=[], push=True
    )

    assert result["plan_id"] == 88
    assert result["pushed"] is True
    assert sent["receiver_ids"] == [40]


def test_training_agent_rejects_unmapped_talent_before_creating_plan(monkeypatch):
    create_plan = MagicMock(return_value=SimpleNamespace(id=88))
    monkeypatch.setattr(PlanService, "create", staticmethod(create_plan))
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, _talent_id: None),
    )

    with pytest.raises(BusinessError, match="未关联有效员工账号"):
        TrainingAgentService.generate_plan(
            MagicMock(), talent_id=145, course_ids=[], push=True
        )

    create_plan.assert_not_called()


def test_manual_training_push_maps_talent_id_to_user_id(monkeypatch):
    db = MagicMock()
    sent = {}
    monkeypatch.setattr(
        PlanDAO,
        "get",
        staticmethod(lambda _db, _pid: SimpleNamespace(id=12, talent_id=5, title="计划")),
    )
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, talent_id: 40 if talent_id == 5 else None),
    )

    def fake_send(_db, **kwargs):
        sent.update(kwargs)
        return SimpleNamespace(id=100)

    monkeypatch.setattr(MessageService, "send", staticmethod(fake_send))

    response = push_plan(12, db)

    assert response["data"] == {"plan_id": 12, "pushed": True}
    assert sent["receiver_ids"] == [40]
    db.commit.assert_called_once()


def test_manual_training_push_rejects_unmapped_talent(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(
        PlanDAO,
        "get",
        staticmethod(lambda _db, _pid: SimpleNamespace(id=12, talent_id=5, title="计划")),
    )
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, _talent_id: None),
    )

    with pytest.raises(BusinessError, match="未关联有效员工账号"):
        push_plan(12, db)
    db.commit.assert_not_called()


def test_create_training_plan_can_push_to_linked_user(monkeypatch):
    db = MagicMock()
    plan = SimpleNamespace(
        id=21,
        talent_id=170,
        title="数据分析进阶计划",
        course_ids="1,2",
        source="manual",
        status=0,
        deadline=None,
        generated_by="管理员",
        weakness_tags="数据分析",
        improvement=0,
        created_at=None,
    )
    body = SimpleNamespace(
        talent_id=170,
        title=plan.title,
        course_ids=[1, 2],
        deadline=None,
        weakness_tags=["数据分析"],
        generated_by="管理员",
        status=0,
        improvement=0,
        push=True,
    )
    sent = {}
    monkeypatch.setattr(PlanService, "create", staticmethod(lambda *_args, **_kwargs: plan))
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, talent_id: 49 if talent_id == 170 else None),
    )
    monkeypatch.setattr(
        MessageService,
        "send",
        staticmethod(lambda _db, **kwargs: sent.update(kwargs)),
    )
    monkeypatch.setattr(training_router.PlanOut, "model_validate", staticmethod(lambda value: value))

    create_plan(body, db)

    assert sent["receiver_ids"] == [49]
    assert sent["biz_type"] == "training"
    assert sent["biz_id"] == 21
    db.commit.assert_called_once()


def test_create_training_plan_rejects_push_without_linked_user(monkeypatch):
    db = MagicMock()
    body = SimpleNamespace(talent_id=999, push=True)
    create = MagicMock()
    monkeypatch.setattr(PlanService, "create", staticmethod(create))
    monkeypatch.setattr(
        MessageService,
        "user_id_for_talent",
        staticmethod(lambda _db, _talent_id: None),
    )

    with pytest.raises(BusinessError, match="未关联有效员工账号"):
        create_plan(body, db)

    create.assert_not_called()
    db.commit.assert_not_called()
