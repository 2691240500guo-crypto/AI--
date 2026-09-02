"""初始化：建表 + 种子数据（超管、根部门、基础菜单/字典）。"""
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.dept import Dept
from app.models.dict_item import DictType
from app.models.menu import Menu
from app.models.user import User
from app.db.seed_assessment import seed_assessment


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

    # 智能培训管理端菜单（T-P5-03）：课程库、学习计划、效果分析
    training_root = db.query(Menu).filter_by(title="智能培训").first()
    if not training_root:
        training_root = Menu(parent_id=0, title="智能培训", path="/training", component="Layout", perm=None, type=1, sort=3)
        db.add(training_root)
        db.flush()

    training_menus = [
        Menu(parent_id=training_root.id, title="课程库管理", path="/training/course", component="training/Course", perm="training:course", type=2, sort=1),
        Menu(parent_id=training_root.id, title="学习计划管理", path="/training/plan", component="training/Plan", perm="training:plan", type=2, sort=2),
        Menu(parent_id=training_root.id, title="培训效果分析", path="/training/effect", component="training/Effect", perm="training:effect", type=2, sort=3),
    ]
    for item in training_menus:
        existing = db.query(Menu).filter_by(title=item.title).first()
        if existing:
            existing.parent_id = training_root.id
            existing.path = item.path
            existing.component = item.component
            existing.perm = item.perm
            existing.type = item.type
            existing.sort = item.sort
        else:
            db.add(item)
    db.flush()

    assessment_root = db.query(Menu).filter_by(title="智能测评").first()
    if not assessment_root:
        assessment_root = Menu(
            parent_id=0,
            title="智能测评",
            icon=None,
            path="/assessment",
            component=None,
            perm=None,
            type=1,
            sort=3,
            status=1,
        )
        db.add(assessment_root)
    else:
        assessment_root.parent_id = 0
        assessment_root.path = "/assessment"
        assessment_root.component = None
        assessment_root.perm = None
        assessment_root.type = 1
        assessment_root.sort = 3
        assessment_root.status = 1
    db.flush()

    assessment_children = [
        ("测评首页", "/assessment/overview", "assessment/overview", "assessment:list", 1),
        ("题库与题目", "/assessment/question-bank", "assessment/questionBank", "assessment:manage", 2),
        ("组卷管理", "/assessment/paper", "assessment/paper", "assessment:paper", 3),
        ("发起测评", "/assessment/launch", "assessment/launch", "assessment:launch", 4),
        ("成绩统计", "/assessment/results", "assessment/results", "assessment:stat", 5),
    ]
    for title, path, component, perm, sort in assessment_children:
        child = db.query(Menu).filter_by(title=title).first()
        if not child:
            child = Menu(parent_id=assessment_root.id, title=title)
            db.add(child)
        child.parent_id = assessment_root.id
        child.path = path
        child.component = component
        child.perm = perm
        child.type = 2
        child.sort = sort
        child.status = 1
    db.flush()

    legacy_assessment_paths = {
        "/assessment/home",
        "/assessment/bank",
        "/assessment/question",
        "/assessment/result",
    }
    legacy_assessment_titles = {"题库管理", "题目管理", "试卷管理", "成绩查询"}
    for item in db.query(Menu).filter(Menu.path.in_(legacy_assessment_paths)).all():
        item.status = 0
    for item in db.query(Menu).filter(Menu.title.in_(legacy_assessment_titles)).all():
        if item.parent_id == assessment_root.id:
            item.status = 0

    answer_menu = db.query(Menu).filter_by(path="/assessment/answer").first()
    if not answer_menu:
        answer_menu = db.query(Menu).filter_by(parent_id=assessment_root.id, title="答题台").first()
    if answer_menu:
        answer_menu.status = 0
    db.flush()

    # 岗位匹配模块菜单（M 域入口）：sys_menu 种入后管理端侧边栏可见，权限码随菜单下发
    matching_root = db.query(Menu).filter_by(title="岗位匹配").first()
    if not matching_root:
        matching_root = Menu(
            parent_id=0,
            title="岗位匹配",
            path="/matching",
            component=None,
            perm="matching:*",
            type=1,
            sort=4,
            status=1,
        )
        db.add(matching_root)
    else:
        matching_root.parent_id = 0
        matching_root.path = "/matching"
        matching_root.component = None
        matching_root.perm = "matching:*"
        matching_root.type = 1
        matching_root.sort = 4
        matching_root.status = 1
    db.flush()

    matching_children = [
        ("岗位管理", "/matching/position", "matching/Position", "matching:position", 1),
        ("匹配结果", "/matching/result", "matching/Result", "matching:result", 2),
        ("岗位人才匹配Agent", "/matching/agent", "matching/Agent", "matching:agent", 3),
        ("储备/空缺预警", "/matching/alert", "matching/Alert", "matching:alert", 4),
    ]
    expected_keys = {(t, p) for t, p, *_ in matching_children}
    for title, path, component, perm, sort in matching_children:
        child = db.query(Menu).filter_by(title=title).first()
        if not child:
            child = Menu(parent_id=matching_root.id, title=title)
            db.add(child)
        child.parent_id = matching_root.id
        child.path = path
        child.component = component
        child.perm = perm
        child.type = 2
        child.sort = sort
        child.status = 1
    db.flush()

    # 去重清洗：删除 matching 根下标题或路径与新清单不一致的旧/残留菜单（避免侧边栏出现重复项）
    # 注意：sys_role_menu 对 sys_menu.id 有外键约束，必须先删关联再删菜单本体
    from app.models.role import RoleMenu

    stale = (
        db.query(Menu)
        .filter(Menu.parent_id == matching_root.id)
        .all()
    )
    for c in stale:
        if (c.title, c.path) not in expected_keys:
            db.query(RoleMenu).filter(RoleMenu.menu_id == c.id).delete(synchronize_session=False)
            db.delete(c)
    db.flush()

    # 数据字典类型
    if not db.query(DictType).first():
        db.add(DictType(code="user_status", name="用户状态"))
        db.add(DictType(code="msg_type", name="消息类型"))

    # 超管账号 admin/admin123：身份由 is_super=1 唯一决定（require_permission 短路、
    # /menus/mine 全量下发），不需要、也不应挂任何"admin 角色"——角色表里没有超管角色，
    # 避免超管角色被误分配/误编辑。仅首次建号；老库已有账号直接跳过。
    if not db.query(User).filter_by(username="admin").first():
        admin = User(username="admin", password=hash_password("admin123"),
                     nickname="超级管理员", is_super=1, dept_id=1, status=1)
        db.add(admin)

    db.commit()


def init_db() -> None:
    """建表 + 播种数据。数据库不可用时打印警告，不阻塞服务启动。
    - 修改人：袁文武  修改时间：2026-09-02
    - 场景：远程 MySQL 网络波动/超时，不应导致整个后端起不来。
    """
    import logging
    logger = logging.getLogger("init_db")
    try:
        create_tables()
    except Exception as e:
        logger.warning("建表失败（数据库可能不可用），跳过初始化：%s", e)
        return
    db = SessionLocal()
    try:
        seed(db)
        seed_assessment(db)
    except Exception as e:
        logger.warning("播种数据失败：%s", e)
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("数据库已初始化，超管账号 admin / admin123")
