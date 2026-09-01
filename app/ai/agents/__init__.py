"""Agent 集合目录（契约 docs/07-Agent接口契约.md 定义 5 个 Agent）。

统一结构：每个 Agent 一个文件。resume/assess/train/query 提供 async run(input_data) -> dict
契约入口；match_agent 为 M 域完整实现（MatchAgent 类：parse_requirement / run_match /
reverse_match / chat），由 matching 路由直接驱动。LangGraph（app/ai/graph.py）复用本层。

| 文件            | Agent | 入口                        | 出参关键字段                |
|-----------------|-------|----------------------------|----------------------------|
| resume_agent.py | ① 简历解析 | async run({file_url,file_type}) | talent_id, tags        |
| assess_agent.py | ② 测评分析 | async run({talent_id,result_id})| report, level, shortcomings|
| match_agent.py  | ③ 岗位匹配 | MatchAgent 类（chat/run_match/reverse_match） | position_id, score |
| train_agent.py  | ④ 培训推送 | async run({talent_id,shortcomings}) | plan_id, course_ids  |
| query_agent.py  | ⑤ NL2SQL   | async run({question})      | sql, columns, rows, chart_json |

使用：from app.ai.agents import resume_agent; await resume_agent.run({...})
"""
