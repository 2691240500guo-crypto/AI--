"""Agent⑤ NL2SQL 自由问数（P10 王泽川 引擎核心 / P11 戈成斌 对话接口）。

D1：只搭骨架，run() 抛 NotImplementedError；D2（T-P6-06）填血肉。
边界约定：P10 负责「schema 约束 + SQL 生成 + 受限执行」，P11 负责对话接口与前端对接。

安全红线（需求 §7.3 D-3）：
  ① 只读连接（使用只授 SELECT 权限的数据库账号）
  ② 表/列白名单 schema 约束（只暴露 tal_/asm_/match_/trn_ 统计口径）
  ③ 生成 SQL 必须过关键字黑名单
  ④ 执行超时上限 5s + 行数上限 1000
  ⑤ Redis 缓存 nl2sql:cache:{hash(question)}（D2 接入）
"""
from typing import Any

from app.utils.logger import logger


class NL2SQLAgent:
    """自然语言 → SQL → 受限执行 → 结果 + 图表配置。"""

    # D2 从 models 元数据自动生成；D1 先留空（空集合表示"尚未开放任何表"）
    ALLOWED_TABLES: set[str] = set()
    # 只允许这些前缀的表进入白名单（需求 §7.3）
    ALLOWED_PREFIXES = ("tal_", "asm_", "match_", "trn_")
    # SQL 关键字黑名单：出现任一即拒答
    BLOCKED_KEYWORDS = {"insert", "update", "delete", "drop", "alter", "truncate",
                        "create", "grant", "revoke", "exec", "union"}
    # 执行限制（D2 生效）
    QUERY_TIMEOUT_SEC = 5
    MAX_ROWS = 1000

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Agent 统一入口。

        入参 input_data: {"question": str, "chart_type": "bar|line|pie"}
        返回: {"sql": str|None, "columns": list, "rows": list, "chart_json": dict|None}
        """
        question: str = input_data.get("question", "")
        chart_type: str = input_data.get("chart_type") or "bar"
        logger.info("Agent⑤ 收到问数请求: %s", question)

        # TODO(D2 - P10): 1) 拼系统提示词（schema + 白名单）→ LLM 生成 SQL
        #   from app.utils.llm import get_llm
        #   prompt = self._build_prompt(question)
        #   sql = get_llm().chat(prompt, system=self._system_prompt())
        #   sql = self._extract_sql(sql)          # 剥掉 LLM 输出的 ```sql 代码块

        # TODO(D2 - P10): 2) 安全校验 → 失败直接拒答，绝不执行
        #   self._assert_safe(sql)                # 黑名单 + 白名单 + 必须 SELECT 开头

        # TODO(D2 - P10): 3) 只读引擎执行（超时 5s / 行数 1000 / 只读账号）
        #   columns, rows = await self._execute_readonly(sql)

        # TODO(D2 - P10): 4) 生成 ECharts 配置，返回 {sql, columns, rows, chart_json}
        #   chart_json = self._build_chart(chart_type, columns, rows)
        #   return {"sql": sql, "columns": columns, "rows": rows, "chart_json": chart_json}

        raise NotImplementedError("Agent⑤ D1 骨架，D2 实现（T-P6-06）")

    # ---------- 以下为 D2 要用的工具方法，D1 先备好（黑名单校验现在就能用）----------

    def _assert_safe(self, sql: str) -> None:
        """SQL 安全校验：不通过直接抛 ValueError，调用方拒答。

        三层防线：① 必须以 SELECT 开头 ② 关键字黑名单 ③ 表白名单
        """
        normalized = " ".join(sql.lower().split())
        if not normalized.startswith("select"):
            raise ValueError("只允许 SELECT 查询")

        # 用词边界匹配，避免 "selection" 之类的误伤
        import re
        for kw in self.BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", normalized):
                raise ValueError(f"SQL 含危险关键字: {kw}")

        # TODO(D2): 解析 FROM/JOIN 后的表名，校验落在 ALLOWED_TABLES 内
        #           未在白名单的表一律拒绝（防止 LLM 幻觉出 sys/user 等敏感表）
        if self.ALLOWED_TABLES:
            pass

    def _build_prompt(self, question: str) -> str:
        """拼接带 schema 约束的提示词（D2 实现）。"""
        # TODO(D2): 从 ALLOWED_TABLES 对应的模型元数据生成建表语句片段，
        #           拼进提示词，把 LLM 的输出牢牢限制在已知 schema 内
        raise NotImplementedError

    def _build_chart(self, chart_type: str, columns: list[str],
                     rows: list[list]) -> dict[str, Any]:
        """按图表类型生成 ECharts option（D2 实现，供 P11 前端直接渲染）。"""
        # TODO(D2): bar/line 取第一列为 x 轴、其余为 series；pie 取第一列+第二列
        raise NotImplementedError


# 单例：避免每次请求重复初始化（D2 里若有 schema 缓存更要复用同一实例）
_agent: NL2SQLAgent | None = None


def get_query_agent() -> NL2SQLAgent:
    """获取 Agent⑤ 全局单例。"""
    global _agent
    if _agent is None:
        _agent = NL2SQLAgent()
    return _agent
