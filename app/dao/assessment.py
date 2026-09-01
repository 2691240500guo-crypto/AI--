"""测评域数据访问：题库 / 题目 / 试卷 / 批次。"""
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.assessment import (
    Paper, PaperQuestion, Question, QuestionBank, Result, ResultDetail,
)


class QuestionBankDAO(BaseDAO[QuestionBank]):
    __model__ = QuestionBank

    @classmethod
    def count(cls, db: Session, keyword: str | None = None, status: int | None = None) -> int:
        stmt = select(func.count()).select_from(QuestionBank)
        if keyword:
            stmt = stmt.where(QuestionBank.name.like(f"%{keyword}%"))
        if status is not None:
            stmt = stmt.where(QuestionBank.status == status)
        return db.scalar(stmt) or 0

    @classmethod
    def paged(cls, db: Session, keyword: str | None = None, status: int | None = None,
              page: int = 1, page_size: int = 20) -> list[QuestionBank]:
        stmt = select(QuestionBank)
        if keyword:
            stmt = stmt.where(QuestionBank.name.like(f"%{keyword}%"))
        if status is not None:
            stmt = stmt.where(QuestionBank.status == status)
        stmt = stmt.order_by(QuestionBank.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())

    @classmethod
    def with_question_count(cls, db: Session, bank: QuestionBank) -> int:
        return db.scalar(
            select(func.count()).select_from(Question).where(Question.bank_id == bank.id)
        ) or 0


class QuestionDAO(BaseDAO[Question]):
    __model__ = Question

    @classmethod
    def count(cls, db: Session, bank_id: int | None = None, type_: str | None = None,
              dimension: str | None = None, difficulty: int | None = None,
              keyword: str | None = None) -> int:
        stmt = select(func.count()).select_from(Question)
        if bank_id is not None:
            stmt = stmt.where(Question.bank_id == bank_id)
        if type_:
            stmt = stmt.where(Question.type == type_)
        if dimension:
            stmt = stmt.where(Question.dimension == dimension)
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        if keyword:
            stmt = stmt.where(Question.content.like(f"%{keyword}%"))
        return db.scalar(stmt) or 0

    @classmethod
    def paged(cls, db: Session, bank_id: int | None = None, type_: str | None = None,
              dimension: str | None = None, difficulty: int | None = None,
              keyword: str | None = None,
              page: int = 1, page_size: int = 20) -> list[Question]:
        stmt = select(Question)
        if bank_id is not None:
            stmt = stmt.where(Question.bank_id == bank_id)
        if type_:
            stmt = stmt.where(Question.type == type_)
        if dimension:
            stmt = stmt.where(Question.dimension == dimension)
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        if keyword:
            stmt = stmt.where(Question.content.like(f"%{keyword}%"))
        stmt = stmt.order_by(Question.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())


class PaperDAO(BaseDAO[Paper]):
    __model__ = Paper

    @classmethod
    def count(cls, db: Session, keyword: str | None = None, status: int | None = None) -> int:
        stmt = select(func.count()).select_from(Paper)
        if keyword:
            stmt = stmt.where(or_(Paper.title.like(f"%{keyword}%"),
                                  Paper.description.like(f"%{keyword}%")))
        if status is not None:
            stmt = stmt.where(Paper.status == status)
        return db.scalar(stmt) or 0

    @classmethod
    def paged(cls, db: Session, keyword: str | None = None, status: int | None = None,
              page: int = 1, page_size: int = 20) -> list[Paper]:
        stmt = select(Paper)
        if keyword:
            stmt = stmt.where(or_(Paper.title.like(f"%{keyword}%"),
                                  Paper.description.like(f"%{keyword}%")))
        if status is not None:
            stmt = stmt.where(Paper.status == status)
        stmt = stmt.order_by(Paper.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())


class ResultDAO(BaseDAO[Result]):
    __model__ = Result

    @classmethod
    def count(cls, db: Session, paper_id: int | None = None, status: int | None = None,
              talent_id: int | None = None) -> int:
        stmt = select(func.count()).select_from(Result)
        if paper_id is not None:
            stmt = stmt.where(Result.paper_id == paper_id)
        if status is not None:
            stmt = stmt.where(Result.status == status)
        if talent_id is not None:
            stmt = stmt.where(Result.talent_id == talent_id)
        return db.scalar(stmt) or 0

    @classmethod
    def paged(cls, db: Session, paper_id: int | None = None, status: int | None = None,
              talent_id: int | None = None, page: int = 1, page_size: int = 20) -> list[Result]:
        stmt = select(Result)
        if paper_id is not None:
            stmt = stmt.where(Result.paper_id == paper_id)
        if status is not None:
            stmt = stmt.where(Result.status == status)
        if talent_id is not None:
            stmt = stmt.where(Result.talent_id == talent_id)
        stmt = stmt.order_by(Result.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())

    @classmethod
    def todo_by_talent(cls, db: Session, talent_id: int) -> list[Result]:
        """某人才的待测/答题中批次。"""
        stmt = (select(Result)
                .where(Result.talent_id == talent_id, Result.status.in_([0, 1]))
                .order_by(Result.id.desc()))
        return list(db.scalars(stmt).all())
