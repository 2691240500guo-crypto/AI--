# C 智能测评报告与培训联动说明

## 1. 本阶段范围

- C06：已交卷测评生成能力报告。
- C07：根据报告短板创建培训联动 outbox。
- 本阶段提供后端能力和管理端 H5 展示，不修改 `miniapp/`。

## 2. 报告生成模式

本地降级模式配置：

```text
ASSESSMENT_REPORT_MODE=local
```

本地模式根据试卷题目快照、逐题得分和能力维度计算报告，不依赖硅基流动、Redis、Milvus 或 MinIO。

默认 Agent 使用硅基流动 OpenAI 兼容接口：

```text
SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_MODEL=deepseek-ai/DeepSeek-V4-Flash
SILICONFLOW_API_KEY=仅通过本机环境变量配置
```

可选配置：

```text
ASSESSMENT_REPORT_MODE=siliconflow
ASSESSMENT_AI_TIMEOUT=20
```

硅基流动调用失败、超时、未配置密钥或返回格式错误时，自动使用本地报告，并在 `fallback_reason` 中记录原因。

## 3. 报告结构

`asm_result.report_json` 保存以下结构：

```json
{
  "version": "1.0",
  "result_id": 1,
  "source": "local",
  "generated_at": "2026-08-31T18:00:00",
  "overall_score": 80.0,
  "overall_rate": 0.8,
  "rating": "良好",
  "radar": [
    {
      "dimension": "项目管理",
      "score": 80.0,
      "total_score": 100.0,
      "rate": 0.8,
      "level": "良好"
    }
  ],
  "strengths": ["项目管理"],
  "weaknesses": ["风险管理"],
  "recommendations": ["建议围绕“风险管理”安排针对性学习和复测。"],
  "fallback_reason": null
}
```

报告只读取 `asm_paper_question` 和 `asm_result_detail` 的历史快照，不读取当前题库答案，因此题库后续修改不会改变历史报告。

岗位演示报告统一使用五个雷达维度：`专业知识`、`业务洞察`、`沟通协作`、`执行管理`、`风险合规`。每个岗位试卷包含每个维度 3 道题，共 15 道题、150 分；雷达值为该维度得分除以该维度快照总分，范围为 0–100%。

## 4. 评级规则

| 得分率 | 评级 |
|---:|---|
| 85% 及以上 | 优秀 |
| 70%–84.99% | 良好 |
| 合格线–69.99% | 合格 |
| 低于合格线 | 待提升 |

默认合格线为 60%，默认短板阈值为 60%。配置项分别为 `ASSESSMENT_PASS_RATE` 和 `ASSESSMENT_WEAK_RATE`。

## 5. 培训联动

报告生成后创建一条 `asm_training_outbox`：

| 状态 | 含义 |
|---|---|
| `pending` | 联动记录已创建，培训计划或消息仍待处理；可手动重试 |
| `sent` | `trn_training_plan` 已落库且员工消息发送成功 |
| `failed` | 计划创建或消息发送失败；保留错误原因和已有 `plan_id`，可重试 |

联动通过培训域公开 `PlanService` 创建 `trn_training_plan`。消息失败时计划不会重复创建；
重试复用 `training_plan_json.plan_id`，状态成功后变为 `sent`。对已经 `sent` 的记录再次重试直接返回原记录，
不会重复创建计划或发送消息。无匹配课程时允许创建 `course_ids` 为空的计划；培训表缺失等数据库错误落为 `failed`。

## 6. LangGraph 联动流程

```text
交卷 -> 创建 Agent Task -> 读取测评/人员上下文 -> Agent②报告分析
                                      |                  |
                                      |          JSON 校验失败
                                      |                  v
                                      |             重试/本地降级
                                      v                  |
                         保存报告 -> 等级同步 -> Agent④培训计划
                                                   |
                                  创建/复用 trn_training_plan
                                      |            |
                                      |失败        v
                                      +-------> failed
                                                   |
                                           pending -> 消息通知
                                                   |       |
                                                   |成功   |失败
                                                   v       v
                                                 sent    failed
```

任务节点、当前节点、重试次数、最终输出和错误原因保存在 `ai_agent_task`；培训计划快照保存在 `asm_training_outbox.training_plan_json`。

## 7. 接口

- `GET /api/v1/assessment/result/{id}/report`：读取已有报告或按需生成。
- `POST /api/v1/assessment/result/{id}/report`：主动生成报告，重复调用返回已有报告。
- `POST /api/v1/assessment/result/{id}/link-training`：创建培训联动任务。
- `GET /api/v1/assessment/result/{id}/training-link`：查看联动状态。
- `POST /api/v1/assessment/result/{id}/training-link/retry`：对 `pending/failed` 记录增加重试次数并幂等重试；`sent` 直接返回。
- `GET /api/v1/assessment/agent-tasks?result_id={id}`：查看该测评的 Agent 任务。
- `GET /api/v1/assessment/agent-tasks/{id}`：查看 Agent 任务状态和状态图快照。

报告和联动接口都复用当前登录鉴权；普通用户只能访问自己的测评结果，超级管理员可以查看全部结果。
