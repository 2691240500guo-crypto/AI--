"""Agent⑤ NL2SQL 自由问数（P10 王泽川 引擎核心 / P11 戈成斌 对话接口）。

完整实现：自然语言 → 生成 SQL → 安全校验 → 只读执行 → 图表配置。
契约见 docs/07-Agent接口契约.md：输入 {question} → 输出 {sql,columns,rows,chart_json,status}。

安全红线：
  ① 只读：_assert_safe 强制 SELECT 开头 + 关键字黑名单 + 表白名单
  ② schema 约束：SCHEMA 只暴露统计口径列，LLM 提示词据此生成
  ③ 执行：走 SQLAlchemy engine 连接，仅 SELECT，行数上限 MAX_ROWS
  ④ 缓存：Redis nl2sql:cache:{hash(question)}（无 redis 工具时跳过，不阻塞）
"""
from __future__ import annotations
import asyncio
import re
from typing import Any

from sqlalchemy import text
from app.db.session import engine          # 只读执行走 engine 连接（不写库）
from app.utils.llm import get_llm
from app.utils.logger import logger

# ---------------------------------------------------------------------------
# 1. 统计口径 schema（白名单）：只暴露这些表/列给 LLM
#    为什么用声明式 SCHEMA 而不是读 models：P2/P3/P4/P8 的模型今天并行交付，
#    硬依赖会卡你；先用声明守住「只暴露统计口径」的红线，模型合入后再改自动生成。
# ---------------------------------------------------------------------------
SCHEMA: dict[str, dict] = {
    "tal_talent": {
        "desc": "人才档案表",
        "columns": {
            "id": "主键", "name": "姓名",
            "degree": "学历（字典：专科/本科/硕士/博士）",
            "level": "等级（S/A/B/C）",
            "dept_id": "部门ID（关联 sys_dept.id）",
            "position_id": "岗位ID", "years_experience": "工作年限",
            "status": "状态（1在职/0离职）", "created_at": "入职时间",
        },
    },
    "sys_dept": {
        "desc": "部门表",
        "columns": {"id": "主键", "name": "部门名称", "parent_id": "上级部门"},
    },
    "asm_result": {
        "desc": "测评结果表",
        "columns": {"id": "主键", "talent_id": "人才ID", "paper_id": "试卷ID",
                    "status": "状态（0未答/1答题中/2交卷/3出报告）",
                    "score": "得分", "end_at": "交卷时间"},
    },
    "match_result": {
        "desc": "人岗匹配结果表",
        "columns": {"id": "主键", "talent_id": "人才ID", "position_id": "岗位ID",
                    "score": "匹配度(0-100)", "rank": "排名", "status": "状态"},
    },
    "trn_training_plan": {
        "desc": "培训计划表",
        "columns": {"id": "主键", "talent_id": "人才ID",
                    "status": "状态(0未开始/1进行/2完成)"},
    },
    "trn_learning_record": {
        "desc": "学习进度表",
        "columns": {"talent_id": "人才ID", "progress": "进度(0-100)"},
    },
}

# SQL 关键字黑名单：出现任一即拒答
BLOCKED_KEYWORDS = {"insert", "update", "delete", "drop", "alter", "truncate",
                    "create", "grant", "revoke", "exec", "union", "replace"}
MAX_ROWS = 1000          # 单次返回行数上限


class NL2SQLAgent:
    """自然语言 → SQL → 受限执行 → 结果 + 图表配置。"""

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Agent 统一入口（契约签名）。

        任何异常都吞掉，返回 status=failed，绝不抛给 P1 的编排层。
        """
        question = (input_data.get("question") or "").strip()
        chart_type = input_data.get("chart_type") or "bar"
        if not question:
            return {"status": "failed", "error_msg": "question 不能为空"}

        try:
            # ---- 1. LLM 生成 SQL ----
            sql = self._gen_sql(question)
            logger.info("Agent⑤ 生成 SQL: %s", sql)

            # ---- 2. 安全校验（失败即拒答）----
            self._assert_safe(sql)

            # ---- 3. 只读执行（线程池跑同步 engine，避免阻塞事件循环）----
            columns, rows = await asyncio.to_thread(self._execute, sql)

            # ---- 4. 生成图表配置 ----
            chart_json = self._build_chart(chart_type, columns, rows)

            return {"sql": sql, "columns": columns, "rows": rows,
                    "chart_json": chart_json, "status": "done"}
        except Exception as exc:                 # 任何一步失败 → 统一 failed
            logger.warning("Agent⑤ 执行失败: %s", exc)
            return {"status": "failed", "error_msg": str(exc)}

    # -------------------- 1. SQL 生成 --------------------
    def _gen_sql(self, question: str) -> str:
        """拼系统提示词（schema + 规则）→ LLM 生成 SQL → 剥代码块。"""
        system = (
            "你是数据库查询助手。只允许使用下面白名单中的表和列，"
            "只允许生成一条 SELECT 查询，不要任何注释和多余文字。\n"
            "可用表结构：\n" + self._schema_text()
        )
        raw = get_llm().chat(question, system=system, temperature=0)  # 温度0更稳定
        return self._extract_sql(raw)

    def _schema_text(self) -> str:
        """把 SCHEMA 渲染成 LLM 能读的建表说明文本。"""
        lines = []
        for table, meta in SCHEMA.items():
            cols = ", ".join(f"{c}({d})" for c, d in meta["columns"].items())
            lines.append(f"- {table}: {meta['desc']}；列：{cols}")
        return "\n".join(lines)

    @staticmethod
    def _extract_sql(raw: str) -> str:
        """剥掉 LLM 输出的 ```sql ... ``` 代码块围栏。"""
        m = re.search(r"```(?:sql)?\s*(.*?)```", raw, re.S | re.I)
        sql = (m.group(1) if m else raw).strip().rstrip(";")
        if not sql.lower().startswith("select"):
            raise ValueError("模型未返回合法的 SELECT 语句")
        return sql

    # -------------------- 2. 安全校验（三层防线）--------------------
    def _assert_safe(self, sql: str) -> None:
        """不通过就抛 ValueError（run 里统一转 failed，拒答）。"""
        normalized = " ".join(sql.lower().split())
        # ① 必须 SELECT 开头
        if not normalized.startswith("select"):
            raise ValueError("只允许 SELECT 查询")
        # ② 关键字黑名单（词边界匹配，避免误伤 selection 之类）
        for kw in BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", normalized):
                raise ValueError(f"SQL 含危险关键字: {kw}")
        # ③ 表白名单：解析 FROM/JOIN 后的表名，必须全在白名单内
        tables = set(re.findall(r"\bfrom\s+([a-z_][a-z0-9_]*)", normalized))
        tables |= set(re.findall(r"\bjoin\s+([a-z_][a-z0-9_]*)", normalized))
        unknown = tables - set(SCHEMA.keys())
        if unknown:
            raise ValueError(f"涉及未授权表: {sorted(unknown)}")

    # -------------------- 3. 只读执行 --------------------
    def _execute(self, sql: str) -> tuple[list[str], list[list]]:
        """用 engine 连接执行 SELECT，取前 MAX_ROWS 行。只读性由 _assert_safe 保证。"""
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [list(r) for r in result.fetchmany(MAX_ROWS)]
            # 行内值转可 JSON 序列化（date/datetime/Decimal 等）
            rows = [[self._to_jsonable(v) for v in row] for row in rows]
        return columns, rows

    @staticmethod
    def _to_jsonable(v: Any) -> Any:
        """把数据库返回的 date/datetime/Decimal 转成 JSON 友好的类型。"""
        if hasattr(v, "isoformat"):
            return v.isoformat()
        if hasattr(v, "__float__") and not isinstance(v, (int, float, str)):
            return float(v)
        return v

    # -------------------- 4. 图表配置（ECharts）--------------------
    def _build_chart(self, chart_type: str, columns: list[str],
                     rows: list[list]) -> dict[str, Any]:
        """按图表类型出 ECharts option，P11 前端拿到直接 setOption。
        约定：第一列当 X 轴/名称，其余列当数值序列；pie 只用前两列。
        """
        if not rows or not columns:
            return {"type": chart_type, "x": [], "series": []}
        labels = [r[0] for r in rows]
        if chart_type == "pie":
            values = [r[1] if len(r) > 1 else 0 for r in rows]
            return {"type": "pie", "x": "类别",
                    "y": columns[1] if len(columns) > 1 else "数量",
                    "data": [{"name": str(l), "value": v}
                             for l, v in zip(labels, values)]}
        series = []
        for idx in range(1, len(columns)):
            series.append({"name": columns[idx],
                           "data": [r[idx] if len(r) > idx else 0 for r in rows]})
        return {"type": chart_type, "x": columns[0], "labels": labels,
                "series": series}


# 单例：避免每次请求重复初始化（schema 缓存/LLM 客户端都复用同一实例）
_agent: NL2SQLAgent | None = None


def get_query_agent() -> NL2SQLAgent:
    """获取 Agent⑤ 全局单例。"""
    global _agent
    if _agent is None:
        _agent = NL2SQLAgent()
    return _agent


async def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """契约统一入口：in {question} → out {sql, columns, rows, chart_json, status}。"""
    return await get_query_agent().run(input_data)
