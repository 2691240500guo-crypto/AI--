"""用户 DAO 示例：演示 BaseDAO + 关联表操作如何写。"""
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.user import User, UserRole


class UserDAO(BaseDAO[User]):
    __model__ = User

    @classmethod
    def count(cls, db: Session, keyword: str | None = None, dept_id: int | None = None,
              status: int | None = None) -> int:
        stmt = select(func.count()).select_from(User)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where((User.username.like(like)) | (User.nickname.like(like)))
        if dept_id:
            stmt = stmt.where(User.dept_id == dept_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        return db.scalar(stmt) or 0

    @classmethod
    def paged(cls, db: Session, keyword: str | None = None, dept_id: int | None = None,
              status: int | None = None, page: int = 1, page_size: int = 20) -> list[User]:
        stmt = select(User)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where((User.username.like(like)) | (User.nickname.like(like)))
        if dept_id:
            stmt = stmt.where(User.dept_id == dept_id)
        if status is not None:
            stmt = stmt.where(User.status == status)
        stmt = stmt.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size)
        return list(db.scalars(stmt).all())

    @classmethod
    def set_roles(cls, db: Session, user_id: int, role_ids: list[int]) -> None:
        db.execute(delete(UserRole).where(UserRole.user_id == user_id))
        for rid in role_ids:
            db.add(UserRole(user_id=user_id, role_id=rid))
        db.flush()