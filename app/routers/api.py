"""统一路由挂载。业务新增模块时在此登记 router，即挂到 /api/v1 之下。"""
from fastapi import APIRouter

from app.routers import auth, user, role, menu, dept, dict_item, message, audit, matching
from app.routers import analytics, training, assessment
from app.routers import talent, talent_dict, resume, course  # hy 分支合并：人才档案/标签/简历/在线学习
from app.routers import kg  # M1 知识图谱（人才关系网 / 相似 / sync-all）
from app.routers import ai_graph  # LangGraph 协同图（三大闭环入口）
from app.routers import ai  # AI 助手对话（J07 小程序端）

api = APIRouter()
api.include_router(auth.router, prefix="/auth", tags=["auth"])
api.include_router(user.router, prefix="/users", tags=["user"])
api.include_router(role.router, prefix="/roles", tags=["role"])
api.include_router(menu.router, prefix="/menus", tags=["menu"])
# 当前用户菜单（仅需登录，供所有角色取菜单），路径已在 mine_router 内定义为 /menus/mine
api.include_router(menu.mine_router, tags=["menu"])
api.include_router(dept.router, prefix="/depts", tags=["dept"])
api.include_router(dict_item.router, prefix="/dicts", tags=["dict"])
api.include_router(message.router, prefix="/messages", tags=["message"])
api.include_router(audit.router, prefix="/audit", tags=["audit"])
api.include_router(matching.router, prefix="/matching", tags=["matching"])
api.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api.include_router(training.router, prefix="/training", tags=["training"])
api.include_router(assessment.router, prefix="/assessment", tags=["assessment"])
# ---- hy 分支合并 ----
api.include_router(talent.router, prefix="/talent", tags=["talent"])
api.include_router(talent_dict.router, prefix="/talent-dicts", tags=["talent-dict"])
api.include_router(resume.router, prefix="/resume", tags=["resume"])
api.include_router(course.router, prefix="/course", tags=["course"])
api.include_router(kg.router, prefix="/kg", tags=["kg"])
api.include_router(ai_graph.router, prefix="/ai/graph", tags=["ai-graph"])
api.include_router(ai.router, prefix="/ai", tags=["ai"])
