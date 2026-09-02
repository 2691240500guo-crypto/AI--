# AI 底座使用说明（供各域复用）

> 岗位匹配模块（M 域）沉淀的 AI 基础设施层，其他域（测评 C、人才 T、简历解析等）可复用。
> 负责人：linsb123 ｜ 最后更新：2026-09-01

---

## 一、AI 底座是什么

AI 底座 = **大模型 + Embedding + 向量数据库** 的统一封装层，是各 AI 功能（解析/匹配/报告/简历/问答）的地基。

| 能力 | 说明 | 对应模块 |
|------|------|---------|
| 🧠 LLM 对话 | 文本理解/生成/结构化抽取 | `app/utils/llm.py` |
| 🔤 Embedding | 文本 → 1024 维向量 | `app/utils/llm.py` |
| 🗄 向量检索 | 高维语义检索 | `app/utils/vector_store.py` |

## 二、组件与版本（勿随意变更）

| 组件 | 值 | 说明 |
|------|----|----|
| LLM 服务 | 硅基流动（SiliconFlow） | `.env` 中 `LLM_STRATEGY="silicon_flow"` |
| 对话模型 | `Qwen/Qwen3-30B-A3B-Instruct-2507` | 文本理解/生成 |
| Embedding 模型 | `BAAI/bge-m3` | **1024 维**，与 Milvus 集合维度对齐 |
| 向量库 | Milvus `v2.4.4`（docker，localhost:19530） | 容器镜像版本勿升 3.x |
| 客户端 | `pymilvus==2.4.9` | **必须 2.4.x，勿升 3.x**（3.x 连 2.4 服务端查询全空） |
| Python | conda 环境 `ai-talent`（3.11） | 统一使用 |

## 三、环境变量（.env）

```ini
# ---------- LLM ----------
LLM_STRATEGY=ollama              # 默认 ollama；切硅基流动用 silicon_flow
SILICON_FLOW_API_KEY=sk-xxxx     # 硅基流动密钥（或 SILICONFLOW_API_KEY）
SILICON_FLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICON_FLOW_LLM_MODEL=Qwen/Qwen3-30B-A3B-Instruct-2507
SILICON_FLOW_EMBED_MODEL=BAAI/bge-m3

# ---------- Milvus ----------
MILVUS_HOST=localhost
MILVUS_PORT=19530
MILVUS_COLLECTION_PREFIX=talent_   # 注意：集合实际名前缀，如 talent_talent_vec
```

> 密钥只放 `.env`，**不提交** git。队友需自行申请硅基流动 key 并配置。

## 四、代码怎么用（两行接入）

### 1. LLM / Embedding（app/utils/llm.py）

```python
from app.utils.llm import get_llm

llm = get_llm()
# 对话（Qwen3-30B）
reply = llm.chat("帮我总结一下", system="你是HR助手")
# 向量化（bge-m3，返回 1024 维 list[float]）
vec = llm.embed("人才画像文本")
```

### 2. 向量库（app/utils/vector_store.py）

```python
from app.utils.vector_store import get_vector_store

vs = get_vector_store()
# 检索（IP 相似度，返回 [{score, text}...]）
hits = vs.search("talent_vec", query_vector, top_k=10)
# 插入
vs.insert("talent_vec", [vector], [text])
# 集合是否存在
vs.has_collection("talent_vec")
# 创建集合（dim 与 bge-m3 对齐 = 1024）
vs.create_collection("talent_vec", dim=1024)
```

## 五、当前已就绪状态

| 项 | 状态 |
|----|------|
| 硅基流动 Qwen3-30B | ✅ 可用（chat 实测正常） |
| bge-m3 Embedding | ✅ 1024 维（embed 实测正常） |
| Milvus 2.4.4 + pymilvus 2.4.9 | ✅ 检索正常 |
| talent_vec（39 人才画像） | ✅ 已向量化 |
| position_vec（7 岗位画像） | ✅ 已向量化 |

## 六、向量化脚本（可复用）

```bash
# 重建人才/岗位向量（--drop 先删旧集合）
conda activate ai-talent
python scripts/vectorize_talents.py --drop
python scripts/vectorize_talents.py --skip-talent --skip-position  # 查看参数
```

> 新增人才/岗位后，重新运行脚本即可增量同步向量。

## 七、常见坑（踩过，勿重复）

1. **pymilvus 3.x 连 Milvus 2.4.4**：`query/search` 全返回空（`stats` 正常）→ **必须 2.4.9**
2. **pymilvus 2.4.9 依赖**：需 `pkg_resources`（从 Python310 复制）+ marshmallow 3.x（`extralibs` 目录 + `.pth` 优先加载，见环境修复记录）
3. **画像文本格式**（硬过滤依赖结构化标记）：
   ```
   【人才id:35|学历:硕士|经验:3年|技能:Python,Java,SQL】姓名：…；专业：…
   【岗位id:1|后端开发工程师】岗位：…；岗位编码：…；岗位说明书：…
   ```
4. **SQLAlchemy 2.0 裸 SQL** 必须 `text()` 包装
5. **Milvus 集合前缀**：`get_vector_store()` 会自动加 `MILVUS_COLLECTION_PREFIX` 前缀（如 `talent_talent_vec`），调用时用短名即可

## 八、队友接入示例（其他域）

```python
# 测评报告生成（C 域示例）
from app.utils.llm import get_llm
llm = get_llm()
report_text = llm.chat(f"根据测评维度得分{score_json}生成报告", system="你是测评分析师")

# 简历解析（T 域示例）
from app.utils.llm import get_llm
parsed = llm.chat(f"解析简历：{resume_text}", system="你是简历解析专家，输出JSON")

# RAG 问答（向量检索 + 生成）
from app.utils.llm import get_llm
from app.utils.vector_store import get_vector_store
hits = get_vector_store().search("knowledge_base", get_llm().embed(question), top_k=5)
answer = get_llm().chat(f"基于资料{ [h['text'] for h in hits] }回答问题：{question}")
```
