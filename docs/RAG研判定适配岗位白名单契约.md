# 跨域需求：RAG 研判"适配岗位"必须限定在岗位管理已存在岗位

## 一、需求背景

当前人才档案 RAG 研判中的"适配岗位"（`fit_positions`）由 LLM 自由生成，未与岗位管理（`pos_position`）数据对齐，可能推荐出**岗位管理里并不存在的岗位名**，导致研判结果与真实的岗位体系脱节。

### 现状链路

- 生成位置：[app/services/resume\_llm\_service.py](file:///d:/project/talent/ai_talent/app/services/resume_llm_service.py) [`EXTRACT_USER_TEMPLATE`](file:///d:/project/talent/ai_talent/app/services/resume_llm_service.py) 中要求 LLM 输出：

  ```json
  "fit_positions": ["最适合 2~4 个岗位类型"]
  ```

- 结果落库：`talent_report.fit_positions`（JSON list）。

- 消费侧：

  - [app/services/talent\_vector\_service.py](file:///d:/project/talent/ai_talent/app/services/talent_vector_service.py) [`_build_dim_texts`](file:///d:/project/talent/ai_talent/app/services/talent_vector_service.py) 将 `fit_positions` 拼入经验向量；

  - `talent_report` 展示接口返回 `fit_positions`。

### 问题

`fit_positions` 由模型自由发挥，未与岗位管理（M 域 `pos_position.name` / `code`）校验或对齐，可能出现"研判说适合××岗位，但系统岗位管理里根本没有这个岗位"。

## 二、预期行为

研判产出的每个 `fit_positions` 名称，必须能在 M 域 `pos_position` 中命中：

- 命中的岗位保留；

- 未命中的岗位丢弃，或归入明确兜底（如"其他"）；

- **禁止把岗位管理里不存在的岗位名写入** **`talent_report.fit_positions`**。

## 三、跨域契约（岗位匹配侧已就绪）

1. **只读复用**：T 域通过公开 service / 只读接口读取岗位清单（字段：`id`、`code`、`name`、`dept_id`、`status`），**不得直接新建/修改** **`pos_position`** **表结构**。

2. **白名单匹配**：建议同时支持 `name` 精确与模糊匹配，且排除停用岗位（`status=0`），以减少 LLM 命名偏差造成的误判。

3. **已就绪岗位示例**（用于对齐）：

   | id | code        | 岗位名称       |
   | -- | ----------- | ---------- |
   | 1  | BE-DEV-01   | 后端开发工程师    |
   | 14 | AI-PM-01    | AI 产品经理    |
   | 15 | AI-ARCH-01  | AI 架构师     |
   | 16 | AIGC-DES-01 | AIGC 内容设计师 |
   | 17 | FE-DEV-01   | 前端开发工程师    |
   | 18 | QA-DEV-01   | 测试开发工程师    |
   | 19 | OPS-01      | 运维工程师      |
   | 20 | HR-ADMIN-01 | HR 专员      |

4. **未命中处理**：无法匹配的岗位名 → 丢弃，并在日志/响应中提示；不要静默写入报告。

## 四、落点与责任人

| 项    | 落点            | 说明                                            |
| ---- | ------------- | --------------------------------------------- |
| 主要改动 | **T 域（人才档案）** | 研判后做岗位校验，或将岗位白名单注入生成 prompt，从源头限定             |
| M 域  | 岗位匹配          | 仅提供只读岗位清单接口，不改表、不写库（岗位数据已在 `pos_position` 就绪） |

> 实现时需 T 域与岗位匹配侧确认接口契约后落地。

