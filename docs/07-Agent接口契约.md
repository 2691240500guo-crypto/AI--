# 07 · Agent 接口契约（v0.1 建议稿 · 待团队确认）

> **状态**：D1 晚发布，D2 开工前各 Agent 负责人确认
> **适用范围**：Agent①-⑤ 实现者 + P1（LangGraph 编排）
> **核心纪律**：改任何输入/输出字段，必须先通知 P1（董任进）与受影响方，禁止静默改字段
> **验收口径**：功能可用（硬）、效果可优化（软）；**LLM 可先 mock，run() 必须能独立跑通**

---

## 0. 为什么要有这份契约

五个 Agent 由 5 组人并行开发，由 P1 用 LangGraph 串联。为避免"各写各的、联调全崩"，约定：

1. 每个 Agent 是**纯函数式组件**：`输入 dict → 输出 dict`，内部自己取数、落库
2. Agent 之间**禁止直接互相调用**，数据靠 State / 数据库 / Milvus 接力
3. P1 只认契约，不关心 Agent 内部实现

---

## 1. 硬性约定（所有人遵守）

| 项 | 约定 |
|----|------|
| 目录 | `app/ai/agents/<name>_agent.py`（resume / assess / match / train / query） |
| 统一签名 | `async def run(input_data: dict) -> dict` |
| 独立性 | 必须可独立运行（`python -m` 或单测），不依赖其他 Agent 存在 |
| LLM 可 mock | 环境无 Ollama 时，返回固定 JSON 也能跑通（验收只看契约，不看效果） |
| 禁止互调 | 不 import 其他 Agent 的 run；接力走 LangGraph State / 落库 / 向量库 |
| 错误处理 | 内部异常返回 `{"status": "failed", "error_msg": "..."}`，不要抛出到编排层 |

---

## 2. 契约总表（一眼版）

| Agent | 负责人 | 输入（P1 传入） | 输出（P1 接收） | 内部落库 |
|-------|--------|----------------|----------------|---------|
| ① 简历解析 | P2/P3 | `{file_url, file_type}` | `{talent_id, tags[], status}` | tal_talent + tal_tag + Milvus(talent_vec) |
| ② 测评分析 | P4/P5 | `{talent_id, result_id}` | `{report, level, shortcomings[], status}` | asm_result.report_json + 回写 tal_talent.level |
| ③ 岗位匹配 | P6/P7 | `{talent_id, position_ids[]}` | `{matches[], status}` | match_result |
| ④ 培训推送 | P8/P9 | `{talent_id, shortcomings[]}` | `{plan_id, course_ids[], status}` | trn_training_plan + MSG 推送 |
| ⑤ NL2SQL | P10/P11 | `{question}` | `{sql, columns, rows, chart_json, status}` | ai_conversation（只读不写业务表） |

---

## 3. 各 Agent 详细契约

### Agent① 简历解析（resume_agent.py）

- **输入**：`{"file_url": "minio://resume/xxx.pdf", "file_type": "pdf|word|image"}`
- **输出**：
  ```json
  {
    "talent_id": 12,
    "tags": ["Python", "FastAPI", "数据分析"],
    "status": "done"
  }
  ```
- **内部流程**：下载文件 → 提取文本 → LLM 抽取结构化字段（name/phone/degree/school/major/skills…）→ 落库 tal_talent + 自动打标签 tal_tag → Embedding 入 Milvus `talent_vec`（供 Agent③ / B07）
- **触发入口**：`POST /talent/parse-resume`（multipart file）
- **注意**：身份证/手机号存库明文、输出脱敏走 `app.utils.masking`（I03）

### Agent② 测评分析（assess_agent.py）

- **输入**：`{"talent_id": 12, "result_id": 8}`
- **输出**：
  ```json
  {
    "report": {"radar": {"逻辑": 80, "表达": 62}, "advice": "..."},
    "level": "B",
    "shortcomings": ["表达能力", "数据分析"],
    "status": "done"
  }
  ```
- **内部流程**：读成绩（asm_result，C 域）→ 读履历（tal_talent，B 域）→ LLM 生成报告 → 写 asm_result.report_json → 回写 tal_talent.level
- **触发入口**：`GET /assessment/result/{id}/report`；联动 `POST /assessment/result/{id}/link-training`
- **注意**：`shortcomings` 是 Agent④ 的输入，**格式定死为字符串数组**，缺一不可

### Agent③ 岗位匹配（match_agent.py）

- **输入**：`{"talent_id": 12, "position_ids": [3, 7, 9]}`
- **输出**：
  ```json
  {
    "matches": [
      {"position_id": 7, "score": 86.5, "explain": "技能匹配度高，欠缺项目管理经验"}
    ],
    "status": "done"
  }
  ```
- **内部流程**：Milvus 检索人才向量（talent_vec，Agent① 产）→ 检索岗位向量（position_vec，D02 产）→ 硬过滤 + 加权算分（规则代码，不调 LLM）→ LLM 生成解释 → 落 match_result
- **触发入口**：`POST /matching/match`

### Agent④ 培训推送（train_agent.py）

- **输入**：`{"talent_id": 12, "shortcomings": ["表达能力", "数据分析"]}`
- **输出**：
  ```json
  {
    "plan_id": 5,
    "course_ids": [101, 204],
    "status": "done"
  }
  ```
- **内部流程**：读岗位能力要求（D02 岗位画像）→ LLM 按短板+能力选课 → 建 trn_training_plan → `notify("training", [talent_id], "…")` 一行推送（H03）
- **触发入口**：`POST /training/plans`（source=agent）；联动 `POST /assessment/result/{id}/link-training`

### Agent⑤ NL2SQL（query_agent.py）

- **输入**：`{"question": "统计各部门硕士人数"}`
- **输出**：
  ```json
  {
    "sql": "SELECT dept.name, COUNT(*) FROM tal_talent ...",
    "columns": ["部门", "人数"],
    "rows": [["研发部", 12]],
    "chart_json": {"type": "bar", "x": "部门", "y": "人数"},
    "status": "done"
  }
  ```
- **内部流程**：LLM 依据表结构 schema 生成 SQL → **只读连接**执行（禁写/禁 DDL）→ 猜图表配置 → 写 ai_conversation
- **触发入口**：`POST /analytics/nl2sql`
- **注意**：必须只读（需求 D-3：schema 约束 + 只读连接 + 权限过滤）

---

## 4. LangGraph State 定义（P1 编排用 · Agent 只读写自己字段）

```python
from typing import TypedDict

class AgentState(TypedDict, total=False):
    # 通用
    agent_code: str            # resume / assess / match / train / query
    error: str | None
    # 闭环 A 成长（②→④）
    talent_id: int
    result_id: int | None
    report: dict | None        # Agent② 产物
    level: str | None          # 回写档案等级
    shortcomings: list[str]    # ② 输出 → ④ 输入（接力命门）
    plan_id: int | None        # Agent④ 产物
    retest_count: int          # 复测循环上限（默认 3）
    # 闭环 B 人岗（①→③）
    position_ids: list[int]
    matches: list[dict]        # Agent③ 产物
    # 闭环 C 问数（⑤）
    question: str
    answer: dict               # Agent⑤ 产物
```

任务状态落库 `ai_agent_task`：`agent_code / input_json / output_json / status(pending|running|done|failed) / state_json / error_msg`（由编排层维护，Agent 内部只返回 done/failed）。

---

## 5. 统一代码模板（照抄改业务即可）

```python
# app/ai/agents/xxx_agent.py
"""AgentX 说明。契约见 docs/07-Agent接口契约.md。"""
import json

from app.utils.llm import get_llm
from app.utils.vector_store import get_vector_store
from app.utils.object_storage import get_object_storage


async def run(input_data: dict) -> dict:
    """契约：in {...} → out {...}。失败返回 status=failed + error_msg。"""
    try:
        # 1. 取数（DB / 文件 / 向量）
        # 2. LLM 处理（无 Ollama 时 mock 固定 JSON，验收只看契约）
        llm = get_llm()
        result = await llm.chat(PROMPT.format(...))
        data = json.loads(result)
        # 3. 落库（本域 DAO）+ 向量入库（如需）
        # 4. 返回契约输出
        return {"status": "done", ...}
    except Exception as e:          # noqa: BLE001
        return {"status": "failed", "error_msg": str(e)}
```

---

## 6. 变更流程

1. 想改输入/输出字段 → **先发群里，@P1 + 受影响 Agent 负责人**，确认后再改
2. 状态语义统一：`status ∈ {done, failed}`；failed 必须带 `error_msg`
3. 落库表结构变更 → 走 Alembic 迁移（`PYTHONUTF8=1 alembic revision --autogenerate -m "..."` + `upgrade head`），**禁止手工 ALTER**

---

## 7. 交付前自测清单（每人提交 Agent 前过一遍）

- [ ] `run()` 可独立调用，输入符合契约
- [ ] 输出 JSON 字段与本文档一致（缺字段 = 打回）
- [ ] 落库表正确、无脏数据
- [ ] 异常路径返回 `{"status": "failed", "error_msg": "..."}`
- [ ] 无 Ollama 环境时用 mock 数据也能跑通（演示降级预案）
- [ ] 自测结果贴到群里，P1 据此接入 StateGraph
