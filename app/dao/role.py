"""角色 DAO（A05 RBAC）。"""
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.role import Role, RoleMenu


class RoleDAO(BaseDAO[Role]):
    __model__ = Role

    @classmethod
    def set_menus(cls, db: Session, role_id: int, menu_ids: list[int]) -> None:
        db.execute(delete(RoleMenu).where(RoleMenu.role_id == role_id))
        for mid in menu_ids:
            db.add(RoleMenu(role_id=role_id, menu_id=mid))
        db.flush()

    @classmethod
    def delete(cls, db: Session, obj: Role) -> None:
        """删除角色前先清理角色-菜单关联，避免外键约束报错。"""
        db.execute(
            delete(RoleMenu).where(RoleMenu.role_id == obj.id),
            execution_options={"synchronize_session": False},
        )
        # 清除 ORM 已加载的关联缓存，避免 StaleDataError
        db.expire(obj)
        super().delete(db, obj)
