"""初始化：建表 + 种子数据（超管、根部门、基础菜单/字典）。"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.dept import Dept
from app.models.dict_item import DictType
from app.models.menu import Menu
from app.models.role import Role
from app.models.user import User, UserRole


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)


def seed(db: Session) -> None:
    # 根部门
    if not db.query(Dept).first():
        db.add(Dept(id=1, name="总部", parent_id=0, sort=1))

    # 根菜单/权限码（按本期 A 模块预置；二期续业务权限）
    menus = [
        Menu(parent_id=0, title="系统管理", path="/system", component="Layout", sort=1),
        Menu(parent_id=1, title="用户管理", path="/system/user", component="system/User", perm="system:user", sort=1),
        Menu(parent_id=1, title="角色管理", path="/system/role", component="system/Role", perm="system:role", sort=2),
        Menu(parent_id=1, title="菜单管理", path="/system/menu", component="system/Menu", perm="system:menu", sort=3),
        Menu(parent_id=1, title="部门管理", path="/system/dept", component="system/Dept", perm="system:dept", sort=4),
        Menu(parent_id=1, title="数据字典", path="/system/dict", component="system/Dict", perm="system:dict", sort=5),
        Menu(parent_id=1, title="操作日志", path="/system/log", component="system/Log", perm="system:audit", sort=6),
        Menu(parent_id=1, title="登录日志", path="/system/login-log", component="system/LoginLog", perm="system:audit", sort=7),
        Menu(parent_id=0, title="消息中心", path="/message", component="Message", perm="system:message", sort=2),
    ]
    # 按 title 幂等补插（已存在则跳过，保证老库升级也能补上新菜单）
    for m in menus:
        if not db.query(Menu).filter_by(title=m.title).first():
            db.add(m)
    db.flush()

    # 数据字典类型
    if not db.query(DictType).first():
        db.add(DictType(code="user_status", name="用户状态"))
        db.add(DictType(code="msg_type", name="消息类型"))

    # 超管角色
    role = db.query(Role).filter_by(code="admin").first()
    if not role:
        role = Role(code="admin", name="超级管理员")
        db.add(role)
        db.flush()

    # 超管账号 admin/admin123
    if not db.query(User).filter_by(username="admin").first():
        admin = User(username="admin", password=hash_password("admin123"),
                     nickname="超级管理员", is_super=1, dept_id=1, status=1)
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role_id=role.id))

    # 给 super admin 角色挂所有菜单
    for m in db.query(Menu).all():
        from app.models.role import RoleMenu
        if not db.query(RoleMenu).filter_by(role_id=role.id, menu_id=m.id).first():
            db.add(RoleMenu(role_id=role.id, menu_id=m.id))

    db.commit()


def init_db() -> None:
    create_tables()
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("数据库已初始化，超管账号 admin / admin123")