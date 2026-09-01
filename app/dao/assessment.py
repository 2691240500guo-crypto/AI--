"""C 智能测评数据访问层。业务规则由 assessment service 负责。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.assessment import (
    AssessmentAnswerEvent,
    AssessmentBatch,
    AssessmentCapabilityModel,
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentResultDetail,
    AssessmentTrainingOutbox,
    PaperQuestion,
    QuestionBank,
)
from app.models.user import User


class QuestionBankDAO(BaseDAO[QuestionBank]):
    __model__ = QuestionBank

    @classmethod
    def paged(cls, db: Session, *, keyword: str | None = None, status: int | None = None,
              page: int = 1, page_size: int = 20) -> tuple[list[QuestionBank], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        if keyword:
            condition = cls.__model__.name.like(f"%{keyword}%")
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if status is not None:
            condition = cls.__model__.status == status
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = list(db.scalars(stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
        return rows, db.scalar(count_stmt) or 0


class AssessmentQuestionDAO(BaseDAO[AssessmentQuestion]):
    __model__ = AssessmentQuestion

    @classmethod
    def paged(cls, db: Session, *, bank_id: int | None = None, question_type: str | None = None,
              dimension: str | None = None, difficulty: int | None = None,
              status: int | None = None, page: int = 1, page_size: int = 20) -> tuple[list[AssessmentQuestion], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        conditions = []
        if bank_id is not None:
            conditions.append(cls.__model__.bank_id == bank_id)
        if question_type:
            conditions.append(cls.__model__.type == question_type)
        if dimension:
            conditions.append(cls.__model__.dimension == dimension)
        if difficulty is not None:
            conditions.append(cls.__model__.difficulty == difficulty)
        if status is not None:
            conditions.append(cls.__model__.status == status)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        rows = list(db.scalars(stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
        return rows, db.scalar(count_stmt) or 0

    @classmethod
    def list_by_bank(cls, db: Session, bank_id: int, *, active_only: bool = False) -> list[AssessmentQuestion]:
        stmt = select(cls.__model__).where(cls.__model__.bank_id == bank_id)
        if active_only:
            stmt = stmt.where(cls.__model__.status == 1)
        return list(db.scalars(stmt.order_by(cls.__model__.id.asc())).all())


class AssessmentPaperDAO(BaseDAO[AssessmentPaper]):
    __model__ = AssessmentPaper

    @classmethod
    def paged(cls, db: Session, *, keyword: str | None = None, status: int | None = None,
              page: int = 1, page_size: int = 20) -> tuple[list[AssessmentPaper], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        if keyword:
            condition = cls.__model__.title.like(f"%{keyword}%")
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        if status is not None:
            condition = cls.__model__.status == status
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        rows = list(db.scalars(stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
        return rows, db.scalar(count_stmt) or 0


class AssessmentCapabilityModelDAO(BaseDAO[AssessmentCapabilityModel]):
    __model__ = AssessmentCapabilityModel

    @classmethod
    def paged(cls, db: Session, *, keyword: str | None = None, status: int | None = None,
              page: int = 1, page_size: int = 100) -> tuple[list[AssessmentCapabilityModel], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        conditions = []
        if keyword:
            conditions.append(cls.__model__.name.like(f"%{keyword}%"))
        if status is not None:
            conditions.append(cls.__model__.status == status)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        rows = list(db.scalars(stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)).all())
        return rows, db.scalar(count_stmt) or 0


class AssessmentBatchDAO(BaseDAO[AssessmentBatch]):
    __model__ = AssessmentBatch

    @classmethod
    def paged(cls, db: Session, *, paper_id: int | None = None, status: int | None = None,
              page: int = 1, page_size: int = 20) -> tuple[list[AssessmentBatch], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        conditions = []
        if paper_id is not None:
            conditions.append(cls.__model__.paper_id == paper_id)
        if status is not None:
            conditions.append(cls.__model__.status == status)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        rows = list(db.scalars(
            stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all())
        return rows, db.scalar(count_stmt) or 0


class PaperQuestionDAO(BaseDAO[PaperQuestion]):
    __model__ = PaperQuestion

    @classmethod
    def list_by_paper(cls, db: Session, paper_id: int) -> list[PaperQuestion]:
        stmt = select(cls.__model__).where(cls.__model__.paper_id == paper_id)
        return list(db.scalars(stmt.order_by(cls.__model__.sort.asc())).all())


class AssessmentResultDAO(BaseDAO[AssessmentResult]):
    __model__ = AssessmentResult

    @classmethod
    def list_by_talent(cls, db: Session, talent_id: int) -> list[AssessmentResult]:
        stmt = select(cls.__model__).where(cls.__model__.talent_id == talent_id)
        return list(db.scalars(stmt.order_by(cls.__model__.id.desc())).all())

    @classmethod
    def get_for_update(cls, db: Session, result_id: int) -> AssessmentResult | None:
        stmt = select(cls.__model__).where(cls.__model__.id == result_id).with_for_update()
        return db.scalar(stmt)

    @classmethod
    def paged(cls, db: Session, *, talent_id: int | None = None, paper_id: int | None = None,
              batch_id: int | None = None,
              status: int | None = None, page: int = 1, page_size: int = 20,
              pending_only: bool = False) -> tuple[list[AssessmentResult], int]:
        stmt = select(cls.__model__)
        count_stmt = select(func.count()).select_from(cls.__model__)
        conditions = []
        if talent_id is not None:
            conditions.append(cls.__model__.talent_id == talent_id)
        if paper_id is not None:
            conditions.append(cls.__model__.paper_id == paper_id)
        if batch_id is not None:
            conditions.append(cls.__model__.batch_id == batch_id)
        if status is not None:
            conditions.append(cls.__model__.status == status)
        if pending_only:
            conditions.append(cls.__model__.status.in_([0, 1]))
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        rows = list(db.scalars(
            stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all())
        return rows, db.scalar(count_stmt) or 0

    @classmethod
    def get_with_user_and_paper(cls, db: Session, result_id: int):
        stmt = (
            select(cls.__model__, User.nickname, AssessmentPaper.title)
            .join(User, User.id == cls.__model__.talent_id)
            .join(AssessmentPaper, AssessmentPaper.id == cls.__model__.paper_id)
            .where(cls.__model__.id == result_id)
        )
        return db.execute(stmt).first()

    @classmethod
    def paged_with_names(cls, db: Session, *, talent_id: int | None = None, paper_id: int | None = None,
                         batch_id: int | None = None,
                         status: int | None = None, page: int = 1, page_size: int = 20
                         ) -> tuple[list[tuple[AssessmentResult, str, str, str | None, str | None]], int]:
        conditions = []
        if talent_id is not None:
            conditions.append(cls.__model__.talent_id == talent_id)
        if paper_id is not None:
            conditions.append(cls.__model__.paper_id == paper_id)
        if batch_id is not None:
            conditions.append(cls.__model__.batch_id == batch_id)
        if status is not None:
            conditions.append(cls.__model__.status == status)
        stmt = (
            select(cls.__model__, User.nickname, AssessmentPaper.title, AssessmentBatch.batch_no, AssessmentBatch.name)
            .join(User, User.id == cls.__model__.talent_id)
            .join(AssessmentPaper, AssessmentPaper.id == cls.__model__.paper_id)
            .outerjoin(AssessmentBatch, AssessmentBatch.id == cls.__model__.batch_id)
        )
        count_stmt = select(func.count()).select_from(cls.__model__)
        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)
        rows = list(db.execute(
            stmt.order_by(cls.__model__.id.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all())
        return rows, db.scalar(count_stmt) or 0

    @classmethod
    def list_completed(cls, db: Session, *, talent_id: int | None = None,
                       paper_id: int | None = None, batch_id: int | None = None) -> list[AssessmentResult]:
        conditions = [cls.__model__.status.in_([2, 3])]
        if talent_id is not None:
            conditions.append(cls.__model__.talent_id == talent_id)
        if paper_id is not None:
            conditions.append(cls.__model__.paper_id == paper_id)
        if batch_id is not None:
            conditions.append(cls.__model__.batch_id == batch_id)
        stmt = select(cls.__model__).where(*conditions).order_by(cls.__model__.id.asc())
        return list(db.scalars(stmt).all())


class AssessmentResultDetailDAO(BaseDAO[AssessmentResultDetail]):
    __model__ = AssessmentResultDetail

    @classmethod
    def list_by_result(cls, db: Session, result_id: int) -> list[AssessmentResultDetail]:
        stmt = select(cls.__model__).where(cls.__model__.result_id == result_id)
        return list(db.scalars(stmt.order_by(cls.__model__.id.asc())).all())


class AssessmentAnswerEventDAO(BaseDAO[AssessmentAnswerEvent]):
    __model__ = AssessmentAnswerEvent

    @classmethod
    def list_by_result(cls, db: Session, result_id: int) -> list[AssessmentAnswerEvent]:
        stmt = select(cls.__model__).where(cls.__model__.result_id == result_id)
        return list(db.scalars(stmt.order_by(cls.__model__.id.asc())).all())


class AssessmentTrainingOutboxDAO(BaseDAO[AssessmentTrainingOutbox]):
    __model__ = AssessmentTrainingOutbox

    @classmethod
    def get_by_result(cls, db: Session, result_id: int) -> AssessmentTrainingOutbox | None:
        return cls.get_by(db, result_id=result_id)
