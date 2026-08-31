# AI 数字化人才平台 · Bug 修复记录

> 版本：v1.1　日期：2026-08-31（三日冲刺 D1）
> 记录范围：基座开发期发现并修复的全部 Bug（14 个）
> 目的：沉淀踩坑经验，避免后人重复踩；新 Bug 按编号追加

---

## 修复统计

| 类别 | 数量 |
|------|------|
| 后端逻辑/断链 | 6 |
| 前端功能缺失/交互 | 5 |
| 环境/配置 | 3 |
| **合计** | **14** |

---

## Bug 列表（按时间顺序）

### BUG-001 审计不落库：操作日志形同虚设 【后端·断链】

- **级别**：🔴 严重（验收线 I01 直接挂）
- **症状**：`AuditMiddleware` 采集了请求信息但 `sys_operation_log` 永远是空表
- **根因**：`middleware/audit.py` 只把数据塞进 `request.state.audit`，全项目没有任何地方调用 `services/audit.py` 的 `record_op()` 写库
- **修复**：`middleware/audit.py` 重写——写操作（POST/PUT/DELETE/PATCH）落库；解析 token 关联 user_id/username；request_body 密码/token 脱敏为 `***`；独立 SessionLocal 会话，写库失败静默不影响主请求
- **涉及文件**：`app/middleware/audit.py`、`app/routers/audit.py`、`app/schemas/log.py`
- **教训**：中间件"采集了数据"≠"写库了"，采集端和消费端必须闭环验证

### BUG-002 auth 路由无 commit：登录日志不落库 【后端·断链】

- **级别**：🔴 严重
- **症状**：`sys_login_log` 永远 0 行，`last_login_at` 不更新
- **根因**：`AuthService.authenticate` 只 `db.flush()`，但 `routers/auth.py` 从不 `db.commit()`，session 关闭时回滚
- **修复**：`routers/auth.py` 登录后补 `db.commit()`
- **涉及文件**：`app/routers/auth.py`
- **教训**：`flush` 只发 SQL 不提交，事务最终靠 `commit`；路由层必须显式提交写操作

### BUG-003 补 commit 后 admin 密码被清空 【后端·数据损坏】

- **级别**：🔴 严重（数据损坏）
- **症状**：修完 BUG-002 后，admin 密码哈希变成空字符串，登录失败
- **根因**：`AuthService.authenticate` 里有 `user.password = ""`（本意"响应不带密码"），它直接改 ORM 对象属性；之前不 commit 无影响，一 commit 就把空密码写进数据库
- **修复**：删除 services/auth.py、routers/auth.py、routers/user.py 共 7 处多余的 `password = ""` 置空（`UserOut` schema 本就不含 password 字段，靠 schema 控制响应即可），重置 admin 密码哈希
- **涉及文件**：`app/services/auth.py`、`app/routers/auth.py`、`app/routers/user.py`
- **教训**：**永远不要为"响应不含某字段"去改 ORM 对象属性**——应该靠序列化 schema 控制；改 ORM 对象 = 可能写库

### BUG-004 BaseDAO 误用：四个路由全部崩溃 【后端·框架设计】

- **级别**：🔴 严重（接口 500）
- **症状**：`POST /roles` 等接口报 `TypeError: BaseDAO.get_by() takes 2 positional arguments but 3 were given`
- **根因**：role/dept/dict/message 路由误写 `BaseDAO.get_by(db, Role, code=...)`、`BaseDAO.get(db, Model, id)` —— 但 BaseDAO 是**类方法**（`cls.__model__` 已绑定模型），不能把模型当第三参数传。这些接口"写了但从未被真正测过"
- **修复**：新建 `dao/role.py`、`dao/dept.py`、`dao/dict_item.py`、`dao/message.py` 子类 DAO（继承 BaseDAO 标注 `__model__`），重写四个路由
- **涉及文件**：`app/dao/{role,dept,dict_item,message}.py`（新建）、`app/routers/{role,dept,dict_item,message}.py`
- **教训**：继承 BaseDAO 的子类才携带模型；新接口写完必须实测，不能只写不测

### BUG-005 角色删除外键崩溃 【后端·外键约束】

- **级别**：🟡 中等
- **症状**：删除角色报 `IntegrityError: foreign key constraint fails (sys_role_menu)`
- **根因**：删除角色未先清理 `sys_role_menu` 关联表
- **修复**：`RoleDAO.delete` 先删关联（`synchronize_session=False` + `db.expire` 防 StaleDataError）
- **涉及文件**：`app/dao/role.py`
- **教训**：删除带外键关联的父表，必须先清理子表关联

### BUG-006 审计查询 total 统计不带条件 【后端·逻辑错误】

- **级别**：🟡 中等
- **症状**：操作日志分页 total 恒为全表总数，筛选后总数错误
- **根因**：`routers/audit.py` 的 `total = db.scalar(select(func.count()).select_from(OperationLog))` 没带 where 条件
- **修复**：total 查询补上与列表一致的 conds
- **涉及文件**：`app/routers/audit.py`
- **教训**：count 查询必须与列表查询共用同一组过滤条件

### BUG-007 登录"点了没反应"：错误被吞 【前端·异常处理】

- **级别**：🔴 严重（无法登录）
- **症状**：点登录按钮，loading 转一下就关，不跳转、无提示、无报错
- **根因**：`views/login/index.vue` 的 try 块**没有 catch**，`user.login()` 任何阶段抛错（登录/loadMenus/registerDynamicRoutes）都被吞掉
- **修复**：try 加 `catch (e) { ElMessage.error(e?.message || '登录失败') }`
- **涉及文件**：`admin_web/src/views/login/index.vue`
- **教训**：**try 必须配 catch**，否则错误被吞，调试时只剩"loading 关了但没反应"，无从下手

### BUG-008 动态路由 addRoute 找不到父路由 【前端·路由】

- **级别**：🔴 严重（动态路由全挂）
- **症状**：登录后菜单即使有数据，动态注册的路由也不生效
- **根因**：`router/index.js` 根路由没设 `name`，`router.addRoute('/', child)` 找不到父路由
- **修复**：根路由加 `name: 'root'`，改 `router.addRoute('root', child)`；component 兜底为 `not-found.vue` 防止 null 导致跳转崩
- **涉及文件**：`admin_web/src/router/index.js`
- **教训**：`addRoute(parentName, route)` 的 parentName 必须是已注册的路由 name，路径不行

### BUG-009 登录后侧边栏空白 【前端·CSS 布局】

- **级别**：🟡 中等（页面全不可用）
- **症状**：登录成功跳到 dashboard，但左侧只有 logo 文字，9 个菜单全部不可见（DOM 存在但看不到）
- **根因**：`.aside` 是默认 block 布局（非 flex），`el-menu` 没有显式高度，子菜单被压成 0 高度
- **修复**：`.aside` 加 `display: flex; flex-direction: column`；`.aside-menu` 加 `flex: 1; overflow-y: auto; border-right: 0 !important`
- **涉及文件**：`admin_web/src/layout/index.vue`
- **教训**：Element Plus 的 el-menu 在非 flex 容器里可能高度塌陷，侧边栏容器必须 flex 布局

### BUG-010 用户编辑无法绑定角色（用户发现）【前端·功能缺失】

- **级别**：🟡 中等（RBAC 链路断）
- **症状**：编辑用户时没有"角色"字段，`role_ids` 永远传不出去，p1-p12 建了无法分配权限
- **根因**：前端 user.vue 缺角色选择 UI（后端 schema/service 一直支持）
- **修复**：user.vue 表单加角色多选（el-select multiple）、回显 row.roles、保存带 role_ids；表格加"角色"列
- **涉及文件**：`admin_web/src/views/system/user.vue`
- **教训**：前端与后端 schema 要对齐验证——后端支持的能力前端要暴露，否则就是"能用但没入口"

### BUG-011 /menus/mine 普通用户必然 403 【前端+后端·权限设计】

- **级别**：🔴 严重（测试 BUG-010 时挖出的更深漏洞）
- **症状**：非超管用户（如 p2）访问 `/menus/mine` 返回 403，登录后侧边栏必然空白
- **根因**：`/menus/mine` 挂在 `router = APIRouter(dependencies=[Depends(require_permission("system:menu"))])` 之下，router 级权限对**所有**路由生效；`dependencies=[]` 不能覆盖 router 级要求。普通用户没有"菜单管理"权限码 → 403
- **修复**：`my_menus` 拆到独立 `mine_router`（仅需登录），`api.py` 单独挂载
- **涉及文件**：`app/routers/menu.py`、`app/routers/api.py`
- **教训**：`APIRouter(dependencies=[...])` 是全局强制，路由级 `dependencies=[]` 只增不减；"所有登录用户都要用"的接口绝不能挂在权限 router 下

### BUG-012 编辑用户密码被强制必填（用户发现）【前端·校验】

- **级别**：🟡 中等
- **症状**：编辑用户时密码必填，不填无法保存；但 placeholder 写着"留空则不修改"，自相矛盾
- **根因**：前端 rules 把 password 写死 `required: true`；后端 `UserUpdate.password` 本来就是选填（`str | None = None`）
- **修复**：user.vue 拆分 rules/editRules——新增时密码必填，编辑时选填（留空不修改）
- **涉及文件**：`admin_web/src/views/system/user.vue`
- **教训**：前端校验要与后端 schema 对齐；"新增必填、编辑选填"是通用场景，用两套 rules

### BUG-013 环境/配置类问题（3 个）【环境·配置】

#### 13.1 jose 老包阻塞启动（`pip install jose` 误装陷阱）
- **症状**：`SyntaxError: Missing parentheses in call to 'print'`，来自 `site-packages\jose.py`
- **根因**：环境装的是 2013 年老包 `jose==1.0.0`（Python 2 语法单文件），项目需要 `python-jose`（包目录 jose/）
- **修复**：卸载 + 手动删 `jose.py` 和损坏的 `~ose-1.0.0.dist-info` + 装 `python-jose[cryptography]==3.3.*`
- **教训**：`pip install jose` ≠ `pip install python-jose`；site-packages 里若只有 `jose.py` 单文件（无 jose/ 目录）就是装错了

#### 13.2 `No module named 'app'`（sys.path 问题）
- **症状**：从 app 目录跑 `python main.py` 报 `ModuleNotFoundError: No module named 'app'`
- **根因**：脚本模式下 sys.path 不含项目根目录
- **修复**：main.py 顶部注入 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`
- **教训**：`python app/main.py`（脚本模式）与 `uvicorn app.main:app`（模块模式）的 sys.path 不同，入口要兼容两种

#### 13.3 日志文件散落两处 + .env 读不到（相对路径问题）
- **症状**：从 app 目录启动，日志写到 `app/ai_talent.log`、.env 读不到回退 SQLite 并生成 dev.db
- **根因**：logger.py 和 config.py 都用相对路径，随启动目录漂移
- **修复**：logger 用 `Path(__file__).resolve().parents[2]` 固定根目录；config 用 `PROJECT_ROOT / ".env"` 绝对路径
- **教训**：文件路径必须基于 `__file__` 推算绝对路径，不能依赖 CWD；`parents[2]` 取决于文件深度（logger 在 app/utils/ 比 main 深一层）

---

## 经验总结（反模式清单）

1. **采集 ≠ 消费**：中间件/工具层采集了数据，必须验证下游真正消费（BUG-001/002）
2. **ORM 对象改属性 = 可能写库**：控制响应用 schema，不要改 ORM 对象（BUG-003）
3. **写了必须测**：新接口/新页面写完立刻实测，不能只写不跑（BUG-004）
4. **try 必须配 catch**：错误被吞是最难调的 bug（BUG-007）
5. **router 级 dependencies 是全局强制**：公共接口不要挂权限 router（BUG-011）
6. **前端校验与后端 schema 对齐**：新增必填、编辑选填是通用规则（BUG-012）
7. **路径基于 __file__ 算绝对路径**：别依赖 CWD（BUG-013.3）
8. **包名陷阱**：`jose` 老包 vs `python-jose`（BUG-013.1）
9. **页面刷新要恢复状态**：Pinia store 不会持久化非 token 字段，应用启动/路由守卫要主动重新加载（BUG-014）

---

### BUG-014 刷新网页后左侧菜单丢失 【前端·状态恢复】

- **级别**：🔴 严重（每次刷新都要重新登录才看到）
- **症状**：刷新浏览器（F5）后，左侧侧边栏只剩 logo，9 个菜单全消失
- **根因**：刷新页面 Vue 应用重新初始化，Pinia store 重置（token 从 sessionStorage 恢复，但 `menus`/`perms` 为空数组）；没有自动恢复机制，只有登录时才填充 menus，刷新后没人触发 `loadMenus()`
- **修复**：`App.vue` onMounted 检测"有 token 但无 menus" → 调 `user.loadMenus()` 重新拉取并注册动态路由
- **涉及文件**：`admin_web/src/App.vue`
- **教训**：**Pinia store 不会跨页面刷新保留非 token 字段**（只有显式持久化才存活）；应用入口处要做"状态恢复"，不能假设 login 一定走过

---

## 附录：当前 Git 状态（D1 结束时）

```
2b9ada1 fix: 编辑用户时密码改为选填（留空不修改，与后端行为一致）
c7d4ff9 fix: 用户编辑支持绑定角色 + /menus/mine 权限修复(普通用户403)
ff54b68 docs: 手册补充 clone 需先 cd 到目标目录的注意点
b37c606 docs: 新增基座使用手册（基建+Git使用+FAQ）
722349c feat: AI数字化人才平台基座 v0.1.0
```

> 新 Bug 请按 `BUG-0XX` 编号追加，并补一句"教训"——这是给团队最值钱的资产。
