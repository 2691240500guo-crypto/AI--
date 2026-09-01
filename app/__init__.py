"""AI Talent 后端应用包。

分层约定（单向依赖，禁止逆向）:
    routers → services → dao → model（schemas 各层共用）
目录:
    core      配置/安全/依赖
    db        会话/Base
    models    SQLAlchemy ORM
    schemas   Pydantic 入参出参
    dao       数据访问（通用 CRUD 基类 + 各模块）
    services  业务逻辑
    routers   路由（/api/v1 统一挂载）
    middleware 横切（留痕等）
    utils     响应/分页等工具
"""