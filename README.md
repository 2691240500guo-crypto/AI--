# AI Talent 人才平台 · 使用文档（基座版 v0.1.0）

> 本项目是 **AI 数字化人才平台**，采用 **uni-app+Vue3（小程序）/ Vue3+Element Plus（管理端）/ Python FastAPI（后端）** 技术栈。
> 本文档基于**当前已实现的骨架**编写，明确标注「已实现 / 待实现」，供团队各成员据此开发与联调。
> 当前根目录：`E:\work\table`

---

## 一、已实现清单（当前骨架全貌）

### 后端 `app/` —— 全部已实现并可运行

分层遵循单向依赖：`router → service → dao → model`，扁平结构。

| 模块 | 路由前缀 | 已实现能力 | 对应功能点 |
|------|---------|-----------|-----------|
| 认证 | `/auth` | 账号密码登录、JWT 签发、refresh 续期、logout、微信登录(接口已留，openid 直传) | A01/A02/A03 |
| 用户 | `/users` | 用户 CRUD、分页搜索、角色分配、禁止删自己 | A04 |
| 角色 | `/roles` | 角色 CRUD、绑定菜单权限 | A05 RBAC |
| 菜单 | `/menus` | 菜单/权限码 CRUD、`/menus/mine` 返回当前用户菜单+权限码 | A06 |
| 部门 | `/depts` | 部门树 CRUD（含岗位模型 `Position`） | A07 |
| 字典 | `/dicts` | 字典类型/条目 CRUD、按 type_code 取项 | A11 |
| 消息 | `/messages` | 我的消息分页、发消息、标记已读、未读数；`MessageService.send()` 一行推送（留 pub/全员） | H01-H04 |
| 审计 | `/audit` | 操作日志、登录日志分页查询 | A08/A09/I01/I02 |

**横切能力**
- 鉴权依赖：`get_current_user` + `require_permission("system:xxx")`，超管放行
- 全局操作留痕中间件 `AuditMiddleware`（/api 下自动记录，业务零侵入）
- 统一响应 `{code,message,data}` + 业务异常 `BusinessError`
- `BaseDAO` 通用 CRUD，新表仅需继承并标注 `__model__`
- 启动自动建表 + 种子数据（根部门、菜单、字典、超管角色、`admin/admin123`）

**数据库模型**（SQLAlchemy 2.x，`Base.metadata` 自动建表）：
`sys_user / sys_role / sys_user_role / sys_menu / sys_role_menu / sys_dept / sys_position / sys_dict_type / sys_dict_item / msg_center / sys_operation_log / sys_login_log`

### AI 工具层 `app/utils/` —— 全部已实现（依赖惰性导入，未装不影响启动）

| 文件 | 能力 | 依赖 |
|------|------|------|
| `llm.py` | `LLMClient`：`chat()` 对话、`embed()` 向量化、`list_models()`；单例 `get_llm()` | ollama（惰性） |
| `vector_store.py` | `VectorStore`：建集合、`insert()`、`search()` 相似检索；`get_vector_store()` | pymilvus（惰性） |
| `object_storage.py` | `ObjectStorage`：`put_bytes/get_bytes/remove/list_objects`；`get_object_storage()` | minio（惰性） |
| `rag.py` | `RAGTool`：`add_document()` 切块+入库、`retrieve()` 召回、`ask()` 检索增强问答；`get_rag()` | 复用上面两个 |

> 配置字段已在 `app/core/config.py`（OLLAMA/MILVUS/MINIO），依赖注在 `requirements.txt`（默认不装，按需启用规避 pydantic 冲突）。

### 管理端 `admin_web/`（Vue3 + Element Plus + Pinia + Vite）

| 页面 | 状态 |
|------|------|
| 登录 `/login` | ✅ 已实现（admin/admin123） |
| 主布局 sidebar+顶栏 | ✅ 已实现（菜单动态渲染自 `/menus/mine`） |
| 数据看板 `/dashboard` | ✅ 占位卡片（数据源二期接入） |
| 系统管理-用户管理 `/system/user` | ✅ 已实现（增删改查+搜索，作业务模板） |
| 角色/菜单/部门/字典/日志/消息 | ⏳ 占位页 `placeholder.vue`（照 user.vue 模板填） |
| 请求封装 `request.js` | ✅ token 注入、统一响应、401 用 refresh 自动续期、sessionStorage 存 token |

### 小程序端 `miniapp/`（uni-app + Vue3 + Pinia）

| 页面 | 状态 |
|------|------|
| 登录（含微信登录入口） | ✅ 账号密码已实现；微信 code2session 待接 |
| 首页 + tabBar（首页/消息/我的） | ✅ 已实现 |
| 消息列表+标记已读 | ✅ 已实现（对接 `/messages`） |
| 我的（用户卡片+退出） | ✅ 已实现 |
| 我的档案 / 在线测评 / 在线学习 / AI 助手 | ⏳ Mock 界面（后端 B/C/E 与 Agent 二期接入） |

---

## 二、目录结构

```
E:\work\table
├─ app/                  # FastAPI 后端
│  ├─ core/           配置(config) / 安全(security) / 鉴权(deps)
│  ├─ db/             session / base / init_db(建表+种子)
│  ├─ models/         SQLAlchemy ORM
│  ├─ schemas/        Pydantic 出入参
│  ├─ dao/            BaseDAO 通用CRUD + 各表 DAO
│  ├─ services/       auth/audit/dict/message 业务
│  ├─ routers/        auth/user/role/menu/dept/dict/message/audit + api.py 统一挂载
│  ├─ middleware/     AuditMiddleware 操作留痕
│  └─ utils/          response / pagination / llm / vector_store / object_storage / rag
├─ admin_web/          # 管理端（Vue3+Element Plus）
├─ miniapp/            # 小程序端（uni-app+Vue3）
├─ docs/               # 需求/计划/分工/架构文档
├─ design/             # 原型与 UI 标注
├─ skills/             # 开发辅助 skill
├─ .env / requirements.txt / README.md
```

---

## 三、快速启动

1. 后端（项目根目录，模块模式启动）
   ```
   conda activate talent
   uvicorn app.main:app --reload
   ```
   > ⚠️ 必须从根目录、用模块模式运行，勿直接 `python app/main.py`（sys.path 会错）。
   > 浏览器打开 `http://127.0.0.1:8000/docs`（Swagger）。管理员密码按部署环境设置，不写入仓库。
   > `.env` 通过 `DATABASE_URL` 指向云端 MySQL 8；连接地址和凭据不写入仓库。

4. 数据库迁移（Alembic，表结构版本化）
   ```
   # 改完 models/ 后生成迁移脚本并同步（Windows 需 PYTHONUTF8=1 避免 GBK 编码报错）
   PYTHONUTF8=1 alembic revision --autogenerate -m "描述"
   PYTHONUTF8=1 alembic upgrade head
   alembic current            # 查看当前版本
   alembic downgrade -1       # 回滚一步
   ```
   > 基线版本 `40ffbb1d3136` 已包含现有 12 张表并 stamp 到云端库；以后任何人改模型，走上面的两步即可，禁止手工 ALTER 数据库。

2. 管理端（`admin_web/`）
   ```
   npm install
   npm run dev          # http://127.0.0.1:5173（Vite 已绑定 IPv4 127.0.0.1）
   ```

3. 小程序端（`miniapp/`）
   ```
   npm install
   npm run dev:h5 -- --port 5174   # H5 预览 http://127.0.0.1:5174/#/pages/index/index
   ```
   > 真正的体验用 **微信开发者工具** 导入 `miniapp/dist/dev/mp-weixin`。
   > 根路径 `/` 会 404，实际首页是 `#/pages/index/index`。

---

## 四、接口速览（`/api/v1`）

| 模块 | 接口 |
|------|------|
| 认证 | `POST /auth/login` `POST /auth/refresh` `POST /auth/logout` `POST /auth/wechat` |
| 用户 | `GET/POST /users` `GET/PUT/DELETE /users/{id}` |
| 角色 | `GET/POST /roles` `PUT/DELETE /roles/{id}` |
| 菜单 | `GET/POST /menus` `PUT/DELETE /menus/{id}` `GET /menus/mine` |
| 部门 | `GET/POST /depts` `PUT/DELETE /depts/{id}` |
| 字典 | `GET/POST /dicts/types` `GET /dicts/items/{type_code}` `POST /dicts/items` `DELETE /dicts/items/{id}` |
| 消息 | `GET/POST /messages` `POST /messages/{id}/read` `GET /messages/unread-count` |
| 审计 | `GET /audit/logs` `GET /audit/login-logs` |
| 元 | `GET /health` |

统一响应：`{ "code": 0, "message": "ok", "data": ... }`，分页 data 含 `items + meta{page,page_size,total}`。
鉴权头：`Authorization: Bearer <token>`。

---

## 五、AI 工具层使用示例

```python
from app.utils.rag import get_rag

rag = get_rag()
# 1) 文档入库（自动切块+向量化，写入 Milvus）
rag.add_document("profile", "张三……原简历文本……", source="resume_001")
# 2) 检索增强问答
answer = rag.ask("profile", "张三擅长什么技术？")
```

```python
from app.utils.llm import get_llm
llm = get_llm()
text = llm.chat("你好")                    # 对话（Ollama qwen2.5:7b）
vec = llm.embed("人才简介")               # 向量化（nomic-embed-text）
```

> 使用前需在 `.env` 填好 Ollama/Milvus/MinIO 连接并在本机启动对应服务；也可先跑通 SQLite/无 AI 场景。

---

## 六、后来者如何新增一个业务模块

以「人才档案 talent 模块（CRUD 示例）」为例，五步走：

1. **model**：`models/talent.py` 写 `class Talent(Base)`，并在 `models/__init__.py` 导出
2. **schema**：`schemas/talent.py` 写 Create/Update/Query/Out
3. **dao**：`dao/talent.py` `class TalentDAO(BaseDAO[Talent]): __model__ = Talent`
4. **service**：`services/talent_service.py` 写业务逻辑（复杂逻辑/多表事务在此）
5. **router**：`routers/talent.py`，CRUD 照抄 `user.py`；并在 `routers/api.py` 加
   `api.include_router(talent.router, prefix="/talent", tags=["talent"])`
6. （前端）管理端照 `system/user.vue`，小程序照 `message.vue` 写页面并挂路由

**横切能力接入（业务零侵入）**：
- 权限：路由参数加 `dependencies=[Depends(require_permission("talent:list"))]`
- 操作留痕：已全局自动
- 消息推送：`MessageService.send(db, type_code=..., title=..., content=...)` 一行
- AI：调用 `get_rag()` / `get_llm()` 即可，无需感知底层

---

## 七、已知简化与二期待办

### 已知简化（当前实现）
- 消息接收人/已读者用逗号串存储（`receiver_ids`/`read_ids`），数据量大再拆表
- 登录限流/黑名单需 Redis，本期未启用
- 微信登录未接 `code2session`，由前端直传 openid/测试 code
- AI 工具层为能力底座，5 个 Agent（档案解析/测评分析/岗位匹配/培训推送/NL2SQL）尚未实现
- 业务模块（人才档案/测评/匹配/培训/数据看板）仅有系统模块骨架，前台多为 Mock

### 二期主要待办
- 人才档案 `talent`：模型/接口 + Agent① 简历解析 + 标签
- 智能测评 `assessment`：题库/组卷/结果 + Agent② 分析报告
- 岗位匹配 `matching`：Agent③ 语义匹配
- 培训赋能 `training`：课程/进度 + Agent④ 个性化推送
- 数据决策 `analytics`：看板 + Agent⑤ NL2SQL 问数
- AI 编排域 `ai/`：LangGraph 多 Agent 协同、RAG 知识库落地
- Alembic 迁移、pytest、Redis 限流、对象存储/向量库联调
