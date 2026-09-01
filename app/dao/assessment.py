"""C 智能测评数据访问层。业务规则由 assessment service 负责。"""

from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, selectinload

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

    @classmethod
    def batch_statistics(cls, db: Session, *, batch_id: int | None = None,
                         paper_id: int | None = None) -> list[dict]:
        """按批次 SQL 聚合统计。

        替代旧实现「逐批次 page_size=100000 全量拉结果 + Python 循环聚合」，
        一次 GROUP BY 查询完成 total/completed/pass/avg 聚合，避免远程库多轮往返。
        """
        completed = AssessmentResult.status.in_([2, 3])
        pass_cond = and_(
            completed,
            AssessmentResult.score / AssessmentPaper.total_score >= Decimal("0.60"),
        )
        stmt = (
            select(
                AssessmentBatch.id.label("batch_id"),
                AssessmentBatch.batch_no,
                AssessmentBatch.name,
                AssessmentBatch.paper_id,
                func.count(AssessmentResult.id).label("total_results"),
                func.coalesce(func.sum(case((completed, 1), else_=0)), 0).label("completed_results"),
                func.coalesce(func.sum(case((pass_cond, 1), else_=0)), 0).label("pass_count"),
                func.avg(case((completed, AssessmentResult.score), else_=None)).label("avg_score"),
            )
            .select_from(AssessmentBatch)
            .outerjoin(AssessmentResult, AssessmentResult.batch_id == AssessmentBatch.id)
            .outerjoin(AssessmentPaper, AssessmentPaper.id == AssessmentBatch.paper_id)
            .group_by(AssessmentBatch.id, AssessmentBatch.batch_no, AssessmentBatch.name, AssessmentBatch.paper_id)
            .order_by(AssessmentBatch.id.desc())
        )
        if batch_id is not None:
            stmt = stmt.where(AssessmentBatch.id == batch_id)
        if paper_id is not None:
            stmt = stmt.where(AssessmentBatch.paper_id == paper_id)
        return [dict(row._mapping) for row in db.execute(stmt).all()]


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
        stmt = stmt.options(selectinload(cls.__model__.paper))
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
        stmt = select(cls.__model__).where(*conditions).order_by(cls.__model__.id.asc()).options(
            selectinload(cls.__model__.paper).selectinload(AssessmentPaper.question_links),
            selectinload(cls.__model__.details),
        )
        return list(db.scalars(stmt).all())

    @classmethod
    def statistics(cls, db: Session, *, talent_id: int | None = None,
                   paper_id: int | None = None, batch_id: int | None = None) -> dict:
        """整体统计 SQL 聚合（替代 list_completed 全量加载 + Python 循环聚合）。

        返回 total_results / completed_results / average_score / average_rate /
        pass_count / dimensions（按题目维度快照聚合）。
        """
        completed = cls.__model__.status.in_([2, 3])
        conditions = [completed]
        if talent_id is not None:
            conditions.append(cls.__model__.talent_id == talent_id)
        if paper_id is not None:
            conditions.append(cls.__model__.paper_id == paper_id)
        if batch_id is not None:
            conditions.append(cls.__model__.batch_id == batch_id)

        rate_ok = and_(
            completed, AssessmentPaper.total_score > 0,
            cls.__model__.score / AssessmentPaper.total_score >= Decimal("0.60"),
        )
        agg_stmt = (
            select(
                func.count(cls.__model__.id).label("total_results"),
                func.coalesce(func.sum(case((completed, 1), else_=0)), 0).label("completed_results"),
                func.avg(case((completed, cls.__model__.score), else_=None)).label("avg_score"),
                func.avg(case(
                    (and_(completed, AssessmentPaper.total_score > 0),
                     cls.__model__.score / AssessmentPaper.total_score),
                    else_=None,
                )).label("avg_rate"),
                func.coalesce(func.sum(case((rate_ok, 1), else_=0)), 0).label("pass_count"),
            )
            .select_from(cls.__model__)
            .outerjoin(AssessmentPaper, AssessmentPaper.id == cls.__model__.paper_id)
            .where(*conditions)
        )
        agg = db.execute(agg_stmt).one()._mapping

        dim_stmt = (
            select(
                PaperQuestion.dimension_snapshot.label("dimension"),
                func.coalesce(func.sum(AssessmentResultDetail.score), 0).label("score"),
                func.coalesce(func.sum(PaperQuestion.score_snapshot), 0).label("total_score"),
                func.count(func.distinct(cls.__model__.id)).label("result_count"),
                func.count(func.distinct(PaperQuestion.question_id)).label("question_count"),
            )
            .select_from(cls.__model__)
            .join(PaperQuestion, PaperQuestion.paper_id == cls.__model__.paper_id)
            .outerjoin(
                AssessmentResultDetail,
                and_(
                    AssessmentResultDetail.result_id == cls.__model__.id,
                    AssessmentResultDetail.question_id == PaperQuestion.question_id,
                ),
            )
            .where(*conditions)
            .group_by(PaperQuestion.dimension_snapshot)
            .order_by(PaperQuestion.dimension_snapshot)
        )
        dims = db.execute(dim_stmt).all()
        return {
            "total_results": agg["total_results"] or 0,
            "completed_results": agg["completed_results"] or 0,
            "average_score": agg["avg_score"],
            "average_rate": agg["avg_rate"],
            "pass_count": agg["pass_count"] or 0,
            "dimensions": [dict(d._mapping) for d in dims],
        }


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
