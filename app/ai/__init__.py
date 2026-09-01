"""AI 能力包：Agent 与 LLM 相关实现。

规约（02-项目开发计划.md §7.4）：
  - 每个 Agent 独立文件 ai/agents/<name>_agent.py
  - 统一实现 async def run(input_data) -> dict
  - Agent 之间不直接互调，只经 LangGraph StateGraph 编排（D2 接入）
"""
