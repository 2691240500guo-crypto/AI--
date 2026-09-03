# C 智能测评总体实施规划书

## 1. 文档状态

- 负责人：P12 田涌浩
- 当前状态：已实施；管理端答题台已按最新范围移除
- 本阶段交付范围：C 智能测评后端 + 管理端 H5
- 暂不实施：`miniapp/` 小程序前端、微信登录、微信订阅消息和真机适配
- 实施前提：收到用户明确的“确认执行”后，才允许修改业务代码、安装依赖、执行迁移或启动服务
- 变更原则：优先新增 C 模块独立文件；公共文件只做必要的路由挂载、模型注册、菜单注册和配置接入；不重构无关模块

## 2. 目标与验收闭环

在一台本地开发机上，仅启动 FastAPI 后端和 `admin_web` 管理端 H5，即可完成：

> 登录 → 题库管理 → 题目管理 → 手动/随机组卷 → 发起测评 → 用户端作答与自动判分 → 管理端成绩统计 → 测评详情 → 能力雷达/评级/建议 → 培训联动记录

Redis、Milvus、MinIO、远程数据库、Dify、远程大模型和其他成员尚未完成的模块均不得成为上述闭环的启动前置条件。

## 3. 范围边界

### 3.1 本期包含

- C01：题库和题目 CRUD、分类筛选、本地种子题目
- C02：手动组卷、按条件随机组卷、题目顺序和分值固化
- C03：选择试卷、人才档案、时间范围并发起测评；通过 `sys_user.talent_id` 映射可用员工账号并记录消息
- C04：保留单选/多选/判断、草稿、倒计时、超时和失焦异常记录后端接口；交互页面归用户端，本阶段不在管理端实现
- C05：服务端自动判分、逐题明细、人员/题目/维度/批次统计
- C06：测评详情、能力雷达、优势、短板、评级、提升建议和报告追溯
- C07：培训联动任务；创建 `trn_training_plan` 并发送消息，按 `pending/sent/failed` 保存可重试状态，不影响测评完成
- 临时 SQLite 链路验证、幂等种子数据、自动化测试和操作说明（不改变项目云端 MySQL 默认配置）

### 3.2 本期不包含

- 不修改或实现 `miniapp/` 下任何页面
- 不接微信 AppID、微信订阅消息、微信切屏 API
- 不强制安装或启动 Ollama、Redis、Milvus、MinIO、Dify
- 不在 C 域实现培训页面；通过培训域公开 Service 创建计划并保留标准联动记录
- 不修改人才档案、岗位匹配、培训、数据决策等模块的内部 DAO 和页面
- 不处理当前工作区中与本任务无关的已有修改或删除

## 4. 实现方案

### 4.1 后端分层

保持项目既有单向依赖：

```text
router -> service -> dao -> model
                    |
                    +-> assessment agent/report adapter
                    +-> message service public API
                    +-> training outbox adapter
```

- Router：参数接收、鉴权、统一响应，不写复杂业务和 SQL
- Service：组卷、状态机、作答、事务判分、统计、报告和联动规则
- DAO：C 模块表的查询和持久化，不跨模块直接操作内部表
- Agent/Report Adapter：调用硅基流动 OpenAI 兼容接口；不可用时使用确定性评分模板，输出相同 JSON 结构
- Message Adapter：仅调用现有 `MessageService.send()`；消息失败不回滚已完成的测评事务
- Training Outbox：记录计划落库与消息投递状态；失败后通过既有 `plan_id` 幂等重试

### 4.2 本地独立模式

- 使用独立 SQLite 文件 `assessment_local.db`，已由 `.gitignore` 的 `*.db` 规则排除
- PowerShell 启动脚本只为当前进程设置 `DATABASE_URL`，不覆盖用户 `.env`
- 默认 `ASSESSMENT_REPORT_MODE=siliconflow`；调用异常、超时或未配置密钥后自动降级到本地报告
- 种子脚本按稳定业务键幂等执行，可重复运行，不生成重复题库、试卷和待测任务

### 4.3 数据模型

新增以下业务表，不修改现有系统表结构：

| 表 | 作用 | 关键约束 |
|---|---|---|
| `asm_question_bank` | 题库 | 名称唯一、状态索引 |
| `asm_question` | 题目 | 题库外键；题型/维度/难度索引；选项和标准答案 JSON |
| `asm_capability_model` | 能力模型 | 名称唯一；关联岗位/层级；固化维度、题量、题型、难度和题库规则 JSON |
| `asm_paper` | 试卷 | 标题、时长、总分、`generation_mode`、`capability_model_id`、`generation_rule` 和状态 |
| `asm_paper_question` | 试卷题目快照 | 试卷+题目唯一；固化顺序、题型、分值、维度、题干、选项和答案 |
| `asm_result` | 测评任务与结果 | `talent_id → tal_talent.id`、`user_id → sys_user.id`、试卷、批次、状态、服务端时间窗口、得分、答案、报告和报告来源 JSON |
| `asm_result_detail` | 逐题答题明细 | 结果+题目唯一；用户答案、正误和得分 |
| `asm_assessment_batch` | 测评批次 | 一次发起请求的批次号、试卷、时间窗口和创建人 |
| `asm_answer_event` | 作答异常事件 | 失焦、恢复、超时和客户端事件，仅作审计标记 |
| `asm_training_outbox` | 培训联动记录 | 结果唯一；Agent 任务、培训计划 JSON、`pending/sent/failed`、重试次数和错误原因；`sent` 表示计划与消息均成功 |
| `ai_agent_task` | Agent 执行任务 | 输入/输出/状态 JSON、当前 LangGraph 节点、重试次数和错误信息 |

状态固定为：`0 未答 → 1 答题中 → 2 已交卷 → 3 报告已生成`。重复交卷返回已有结果，不重复创建明细或重复计分。

### 4.4 管理端 H5 页面

智能测评使用一个顶级菜单和一个主页面，主页面通过标签页组织功能，避免改动公共路由机制：

- 题库：题库列表、题目筛选、新增、编辑、停用和删除保护
- 组卷：基本信息、手动选题、随机规则、分值校验和预览
- 发起测评：选择试卷、已关联有效员工账号的人才档案、开始/截止时间和时长；提交 `talent_id`
- 测评首页：统计指标、管理流程说明，以及题库、组卷、发起和成绩四个快速操作入口
- 成绩统计：指标、人员/试卷/批次筛选、结果列表、能力雷达、批次分析、题目分析和详情抽屉
- 测评报告：雷达图、评级、优势、短板、建议、报告来源和培训联动状态；前端显示“待处理/已联动/联动失败”
- 岗位演示题库：内置 HR、销售、设备工程师、策划四类岗位，共 60 道题；每类 15 题，覆盖单选、多选、判断和五个统一能力维度

本阶段使用 ECharts 绘制雷达和统计图。管理端 API 统一放在 `admin_web/src/api/assessment.js`，页面中不直接调用 axios。

## 5. 计划文件变更清单

以下是执行阶段的预计变更。任何新增文件、删除文件或明显超出此表的修改，执行前必须重新说明并等待确认。

### 5.1 计划新增文件

| 文件 | 新增内容 |
|---|---|
| `app/models/assessment.py` | 8 个 C 模块 ORM 模型、索引、唯一约束和关系 |
| `app/schemas/assessment.py` | 题库、题目、试卷、发起、作答、统计、报告和联动请求/响应模型 |
| `app/dao/assessment.py` | C 模块查询、分页、统计聚合和锁定读取 |
| `app/services/assessment_service.py` | CRUD、组卷、发起、草稿、计时、交卷、判分、统计和事务控制 |
| `app/services/assessment_report_service.py` | 维度计算、评级、LangGraph 报告和培训联动入口 |
| `app/agents/__init__.py` | Agent 包初始化 |
| `app/agents/assessment_agent.py` | Agent②硅基流动结构化报告适配和 JSON 校验 |
| `app/agents/siliconflow_client.py` | 硅基流动 OpenAI 兼容接口和超时封装 |
| `app/agents/assessment_graph.py` | LangGraph 报告、等级同步、培训联动状态图 |
| `app/agents/training_agent.py` | Agent④培训计划生成和本地降级 |
| `app/models/agent.py` | `ai_agent_task` Agent 任务状态模型 |
| `app/dao/agent.py` | Agent 任务查询 |
| `app/schemas/agent.py` | Agent 任务响应模型 |
| `app/routers/assessment.py` | `/api/v1/assessment` 全部接口与权限依赖 |
| `app/db/seed_assessment.py` | 幂等本地测试账号、题库、题目、试卷和待测任务 |
| `alembic/versions/<revision>_add_assessment_tables.py` | C 模块表、索引、外键和完整 downgrade |
| `admin_web/src/api/assessment.js` | 管理端 C 模块 API 封装 |
| `admin_web/src/views/assessment/index.vue` | 智能测评主页面、标签页和全局状态 |
| `admin_web/src/views/assessment/components/QuestionBankPanel.vue` | 题库和题目管理 |
| `admin_web/src/views/assessment/components/PaperPanel.vue` | 手动/随机组卷和预览 |
| `admin_web/src/views/assessment/components/LaunchPanel.vue` | 发起测评表单和记录 |
| `admin_web/src/views/assessment/overview.vue` | 测评指标、管理说明和快速操作入口 |
| `admin_web/src/views/assessment/components/ResultsPanel.vue` | 成绩筛选、统计图和列表 |
| `admin_web/src/views/assessment/components/ResultDetailDrawer.vue` | 逐题详情、报告和联动状态 |
| `admin_web/src/views/assessment/components/AssessmentRadar.vue` | ECharts 能力雷达组件 |
| `app/db/assessment_role_questions.py` | HR、销售、设备工程师、策划四类岗位的 60 道演示题目配置 |
| `scripts/run_assessment_local.ps1` | 设置本地环境、迁移、种子初始化并启动后端 |
| `docs/C智能测评本地运行与验收.md` | 启动命令、测试账号、演示步骤、降级模式和常见问题 |

### 5.2 计划修改文件

| 文件 | 删除内容 | 增添/修改内容 | 影响控制 |
|---|---|---|---|
| `app/models/__init__.py` | 无 | 导入并导出 assessment 模型 | 仅确保建表和迁移可识别 |
| `app/routers/api.py` | 无 | 导入 assessment router，并挂载 `/assessment` | 不改变现有路由 |
| `app/db/init_db.py` | 无 | 调用幂等测评种子函数；新增智能测评目录菜单 | 不改现有账号、角色和菜单逻辑 |
| `app/db/seed_assessment.py` | 无 | 创建四类岗位题库、五维能力模型、15 题试卷、批次和已完成报告样本 | 业务唯一名称幂等，不改历史试卷和结果 |
| `app/services/assessment_service.py` | 无 | 增加平均得分率、维度参与人数和题量等统计字段 | 沿用原统计接口和筛选条件 |
| `app/schemas/assessment.py` | 无 | 扩展统计和结果列表响应字段 | 新增字段提供默认值，保持客户端兼容 |
| `admin_web/src/views/assessment/components/ResultsPanel.vue` | 旧的连续堆叠统计区 | 增加能力雷达、批次分析、题目分析页签和统一指标 | 不改变 API 路径 |
| `admin_web/src/views/assessment/components/ResultDetailDrawer.vue` | 固定单一报告布局 | 增加得分概览、维度明细和自适应雷达布局 | 只影响 C 测评结果详情 |
| `app/core/config.py` | 无 | 增加报告模式、AI 超时、默认合格线配置，均有本地默认值 | 不改变现有数据库和 AI 默认配置 |
| `admin_web/package.json` | 无 | 增加 `echarts` 依赖 | 仅管理端使用 |
| `admin_web/package-lock.json` | 无手工删除 | 由 npm 同步 ECharts 锁定版本 | 不升级其他依赖 |
| `AGENTS.md` | 无 | 在用户再次确认后补充“改动前文件级规划与审批门禁” | 只固化协作流程，不改变业务范围 |

### 5.3 明确不修改的文件和目录

- `miniapp/**`
- 现有 `app/models/user.py`、`message.py`、人才/培训等业务模型
- 现有系统管理页面和公共布局
- 当前用户已修改的 `docs/基础框架架构设计.md`
- 当前用户已删除或移动的 `.env.example`
- 用户的 `.env`、真实数据库和真实业务数据

### 5.4 计划删除文件

无。若实施中发现必须删除或替换文件，将停止执行，先说明原因、目标文件和恢复方式，等待再次确认。

## 6. 接口规划

所有路径以 `/api/v1/assessment` 开头，复用现有 `{code, message, data}` 响应结构和登录鉴权。

| 方法与路径 | 用途 |
|---|---|
| `GET/POST /banks` | 题库列表和新增 |
| `GET/PUT/DELETE /banks/{id}` | 题库详情、编辑和受保护删除 |
| `GET/POST /questions` | 题目筛选和新增 |
| `GET/PUT/DELETE /questions/{id}` | 题目详情、编辑和受保护删除 |
| `POST /questions/import` | 本地 JSON/Excel 批量导入，可延后到核心链路完成后 |
| `GET/POST /papers` | 试卷列表和手动/随机组卷 |
| `GET/PUT/DELETE /papers/{id}` | 试卷详情、编辑和受保护删除 |
| `POST /launch` | 发起测评并记录消息 |
| `GET /batches`、`GET /batches/{id}` | 批次分页和批次汇总详情 |
| `GET /launches` | 发起记录列表 |
| `GET /todo` | 当前登录账号待测列表 |
| `GET /result/{id}/answer` | 获取固定题目快照和服务端剩余时间 |
| `POST /result/{id}/answer` | 幂等保存草稿答案 |
| `POST /result/{id}/events` | 记录失焦、恢复等异常事件 |
| `POST /result/{id}/submit` | 幂等交卷和服务端判分 |
| `GET /results` | 成绩分页和筛选 |
| `GET /results/statistics` | 人员、题目、维度和批次统计 |
| `GET /results/statistics/questions` | 按题目统计作答次数、正确次数、正确率和平均得分 |
| `GET /results/statistics/batches` | 批次完成率、合格率和平均分汇总 |
| `GET /result/{id}` | 测评、逐题和异常详情 |
| `POST/GET /result/{id}/report` | 生成或读取结构化报告 |
| `POST /result/{id}/link-training` | 创建或重试培训联动记录 |

具体字段、错误码和示例响应将在实施第一阶段先固化为 schema；若接口契约发生变化，将先更新本规划并请求确认。

## 7. 分阶段执行计划

### 阶段 0：实施前基线确认

- 展示 `git status`，标记用户已有改动
- 记录当前后端健康检查、管理端构建结果和数据库配置
- 不修复任何与 C 模块无关的问题
- 输出最终文件级变更清单，等待一次执行确认

通过条件：用户回复明确同意执行，且清单范围无异议。

### 阶段 1：数据模型与接口契约

- 新增模型、schema、DAO 和 Alembic migration
- 注册模型和 `/assessment` 路由
- 完成题库、题目、试卷和发起测评 CRUD
- 添加幂等种子数据

通过条件：本地 SQLite 可迁移；Swagger 可管理题库、完成组卷并发起测评。

### 阶段 2：作答、判分与统计

- 实现题目快照、草稿、服务端计时和异常事件
- 实现事务交卷、三类题型判分和重复交卷幂等
- 实现逐题、人员、维度和批次统计

通过条件：自动化测试覆盖正常、空答案、超时、重复交卷和历史试卷不变性。

### 阶段 3 增量：测评批次与题目级统计

- 新增 `asm_assessment_batch`，一次发起请求创建一个批次，批次内所有结果共享 `batch_id`
- 结果列表和总览支持按批次筛选；历史结果允许 `batch_id` 为空并继续查询
- 新增批次列表/详情、批次汇总和题目级统计接口，并接入管理端成绩页

通过条件：本地 SQLite 迁移后可完成发起、交卷、批次筛选、批次汇总和题目正确率查询；重复交卷不重复累加统计。

### 阶段 3：报告与培训联动

- 实现确定性本地报告和雷达数据
- 接入硅基流动，配置短超时和自动降级
- 实现培训 outbox、失败状态和重试

通过条件：硅基流动不可用时仍可生成完整报告；培训计划和消息成功后联动为 `sent`，任一步失败为 `failed` 并可幂等重试；可通过 LangGraph 任务接口查看节点状态。

### 阶段 4：管理端 H5

- 新增 API 封装、智能测评菜单和主页面
- 完成首页快速操作、题库、组卷、发起、统计、详情和报告 UI
- 增加 ECharts 雷达及统计图
- 完成加载、空数据、错误、报告生成中和失败重试状态
- 结果分析页统一采用统计接口返回的数据，雷达图使用五维得分率并通过容器尺寸自动重绘

通过条件：管理端 H5 可从登录走通题库、组卷、发起、统计和报告管理链路，页面刷新和窄屏不破坏流程；作答链路通过后端 API 独立验证。

### 阶段 5：本地运行与回归

- 完成本地启动脚本和运行文档
- 执行 C 模块 API 冒烟验证、后端启动检查、临时 SQLite 自动化测试和管理端构建
- 使用种子账号手工联跑核心闭环
- 汇总实际改动、测试结果、未完成项和已知限制

通过条件：无外部服务时完整闭环通过；未触碰小程序和无关模块；`git diff --check` 通过。

## 8. 测试矩阵

| 类型 | 必测场景 |
|---|---|
| 题库 | CRUD、筛选、非法题型、无选项、被试卷引用后的删除保护 |
| 组卷 | 手动/随机、题量不足、重复题、总分不一致、快照不可变 |
| 发起 | 无效人才、未映射员工账号、无效时间、重复发起、消息服务失败降级 |
| 作答 | 三种题型、刷新恢复、草稿覆盖、客户端改时钟、失焦事件、超时 |
| 判分 | 多选无序、漏选、多选、空答案、事务回滚、重复交卷 |
| 统计 | 按人/题/维度/批次、空数据、分页和筛选口径一致 |
| 报告 | 本地报告、硅基流动成功、超时/异常降级、结构化 JSON 校验 |
| 联动 | 空课程、培训表缺失、消息失败、`pending/failed` 重试、`sent` 重复重试、计划和消息幂等 |
| 前端 | 加载、空态、错误、权限、刷新、重复点击、桌面和窄屏 |

上述核心后端场景已通过 `tests/` 中的临时 SQLite 自动化测试覆盖；管理端同时执行生产构建，并保留 Swagger/H5 人工验收。

## 9. 风险与隔离策略

| 风险 | 控制方式 |
|---|---|
| 公共文件冲突 | 公共文件只追加导入、挂载和菜单项；编辑前重新读取，不覆盖用户改动 |
| 云端数据库误写 | 本地脚本显式设置 SQLite；测试使用独立临时数据库 |
| AI 服务不可用 | 本地确定性报告为降级路径；硅基流动为可选增强并设置超时 |
| 培训计划或消息失败 | SAVEPOINT 隔离失败，outbox 记录 `failed`；重试复用已有 `plan_id` |
| 历史题目被修改 | 发起时固化试卷题目快照和分值 |
| 重复交卷重复计分 | 状态检查、数据库唯一约束和同一事务保证幂等 |
| 前端影响公共路由 | 使用现有菜单动态路由，只新增一个 assessment 页面入口 |
| 依赖升级引发回归 | 仅新增固定版本 ECharts，不执行全量依赖升级 |

## 10. 回滚方案

- 所有 C 业务代码尽量位于新文件中，可按模块整体撤回
- Alembic migration 提供完整 `downgrade()`，仅删除新增 C 表和索引
- 公共文件改动均为少量追加项，可逐项反向移除，不替换原逻辑
- 本地 SQLite 文件可删除后由迁移和种子脚本重新生成，不触碰用户真实数据库
- 不使用 `git reset --hard`、`git checkout --` 等会覆盖用户改动的命令

## 11. 后续审批流程

本规划确认后，每个实施阶段开始前仍会先给出简短变更预告，内容包括：

1. 本阶段准备修改和新增的文件
2. 每个文件准备删除、替换或新增的代码内容
3. 对现有模块可能产生的影响及隔离方式
4. 准备执行的迁移、安装、测试和启动命令
5. 是否存在与本规划不同的新变更

若没有超出已确认规划，可在用户确认该阶段后执行；如出现新增文件删除、公共架构调整、接口破坏性变化或额外依赖，必须暂停并再次确认。

## 12. 待确认项

建议按本规划执行，默认采用以下决策：

- 管理端 H5 只提供测评管理、统计和报告功能，在线答题入口归用户端
- SQLite 为本地独立运行默认数据库
- AI 报告默认通过 LangGraph 调用硅基流动，失败时使用本地确定性生成
- ECharts 用于雷达图和统计图
- 小程序本阶段完全不改动
- 仅删除已退出范围的管理端答题台页面和组件，不删除后端作答接口

用户确认方式：回复“确认执行该规划”。在收到确认前，不进入代码实施阶段。
