from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.utils.response import ok

T = TypeVar("T", bound=Base)


@dataclass
class PageParams:
    page: int = Query(1, ge=1, description="页码")
    page_size: int = Query(20, ge=1, le=200, description="每页条数")


def paged_result(items: list, page: int, page_size: int, total: int) -> dict:
    return {
        "items": items,
        "meta": {"page": page, "page_size": page_size, "total": total,
                 "total_pages": (total + page_size - 1) // page_size if page_size else 0},
    }


def count_rows(db: Session, model: type[T], *where) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*where)) or 0