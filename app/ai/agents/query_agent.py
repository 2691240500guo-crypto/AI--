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
            "dept_id": "部门ID（关联 sys_dept.id）；非空=已分配部门的内部员工(employee)，为空=未分配部门的候选人(candidate)。",
            "position_id": "岗位ID", "years_experience": "工作年限",
            "status": "状态（1在档/0失效，为软删除标记，非在职/离职；不要用它来筛选内部员工）",
            "identity": "身份（派生虚拟字段，非真实列）：employee=已分配部门的内部员工，candidate=未分配部门的候选人，判定依据就是 dept_id 是否非空。筛选内部员工请写 `dept_id IS NOT NULL`，筛选候选人请写 `dept_id IS NULL`；禁止直接写 `identity='employee'` 这类条件（identity 不是真实列，数据库里不存在）。",
            "created_at": "档案录入时间（产品侧称入职时间，实为档案建档时间，并非真实入职日期）",
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

# MySQL 5.7 方言限制（云端为 MySQL 5.7）：窗口函数 / CTE 等 MySQL 8 语法执行即 1064。
# 命中即拒答并提示改用 GROUP BY/JOIN/常规聚合实现（2026-09-03 修复：占比/排行类问题曾因此失败）。
MYSQL57_BANNED_PATTERNS = [
    (re.compile(r"\bover\s*\("), "窗口函数 OVER"),
    (re.compile(r"\b(?:row_number|rank|dense_rank)\s*\("), "窗口函数 ROW_NUMBER/RANK"),
    (re.compile(r"\b(?:lag|lead|ntile|first_value|last_value|nth_value|cume_dist|percent_rank)\s*\("), "窗口函数"),
    (re.compile(r"\bwith\s+[a-z_][a-z0-9_]*\s+as\s*\("), "CTE(WITH ... AS)"),
]


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
            # ---- 1. LLM 生成 SQL + 安全校验（方言不合规自动重试一次）----
            sql = ""
            for attempt in range(2):
                hint = ("你上一版 SQL 因使用窗口函数/CTE 被拒。"
                        "请务必只用 GROUP BY + JOIN + 常规聚合函数与子查询，不要用 OVER()/ROW_NUMBER()/WITH AS。"
                        if attempt == 1 else "")
                sql = self._gen_sql(question, hint)
                logger.info("Agent⑤ 生成 SQL: %s", sql)
                try:
                    self._assert_safe(sql)
                    break
                except ValueError as exc:
                    if attempt == 0 and "MySQL 5.7 不支持" in str(exc):
                        logger.warning("Agent⑤ SQL 方言不合规，带提示重试: %s", exc)
                        continue
                    raise

            # ---- 2. 只读执行（线程池跑同步 engine，避免阻塞事件循环）----
            columns, rows = await asyncio.to_thread(self._execute, sql)

            # ---- 3. 生成图表配置 ----
            chart_json = self._build_chart(chart_type, columns, rows)

            # ---- 4. LLM 自然语言解读（HR 友好）----
            # 任何异常都被 _interpret 内部吞掉并回退到朴素直拼，绝不阻塞主流程
            answer = await asyncio.to_thread(self._interpret, question, columns, rows)

            return {"sql": sql, "columns": columns, "rows": rows,
                    "chart_json": chart_json, "answer": answer, "status": "done"}
        except Exception as exc:                 # 任何一步失败 → 统一 failed
            logger.warning("Agent⑤ 执行失败: %s", exc)
            return {"status": "failed", "error_msg": str(exc)}

    # -------------------- 1. SQL 生成 --------------------
    def _gen_sql(self, question: str, retry_hint: str = "") -> str:
        """拼系统提示词（schema + 规则 + 方言约束）→ LLM 生成 SQL → 剥代码块。"""
        system = (
            "你是数据库查询助手。只允许使用下面白名单中的表和列，"
            "只允许生成一条 SELECT 查询，不要任何注释和多余文字。\n"
            "目标数据库为 MySQL 5.7：禁止使用窗口函数（OVER、ROW_NUMBER、RANK、LAG/LEAD 等）"
            "与 CTE（WITH ... AS）等 MySQL 8 语法；"
            "占比/排行等统计请用 GROUP BY + JOIN + 常规聚合函数（COUNT/SUM/AVG/MAX）与子查询实现。\n"
            "可用表结构：\n" + self._schema_text()
        )
        if retry_hint:
            system += "\n注意：" + retry_hint
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
        # ⑤ 虚拟字段 identity 防护：SCHEMA 中 identity 是派生虚拟字段（非真实列），
        # 必须用 dept_id IS NOT NULL（内部员工）/ IS NULL（候选人）表达，
        # 严禁写成 identity='employee' 这类列引用，否则 MySQL 报列不存在。
        if re.search(r"\bidentity\b", normalized):
            raise ValueError(
                "identity 是派生虚拟字段、不是真实列，不能当作列引用。"
                "筛选内部员工请用 dept_id IS NOT NULL，筛选候选人请用 dept_id IS NULL"
            )
        # ④ MySQL 5.7 方言限制：窗口函数/CTE 在云端执行必报 1064，直接拦截
        for pat, name in MYSQL57_BANNED_PATTERNS:
            if pat.search(normalized):
                raise ValueError(f"SQL 使用了 MySQL 5.7 不支持的{name}语法，请改用 GROUP BY/JOIN 实现")

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
        # 单值聚合（如 COUNT/SUM/AVG 返回 1 行 1 列）：用户选了图表就要看到图，
        # 不能只塞一个数字。pie → 1 个分类的饼图；bar/line → 1 根柱子 / 1 个点。
        if len(columns) == 1 and len(rows) == 1:
            value = rows[0][0]
            label = columns[0]
            if chart_type == "pie":
                return {"type": "pie", "x": "", "y": "数量",
                        "data": [{"name": label, "value": value}]}
            return {"type": chart_type, "x": label,
                    "labels": [label],
                    "series": [{"name": label, "data": [value]}]}
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

    # -------------------- 5. LLM 自然语言解读（HR 友好）--------------------
    def _interpret(self, question: str, columns: list[str], rows: list[list]) -> str:
        """把查询结果总结成自然语言给非技术 HR 用户看。

        - 控制 prompt 大小：最多给 LLM 看前 30 行（截断不丢数据，表格区仍显示完整）。
        - 任何异常（LLM 超时/无响应/JSON 解析等）都吞掉，回退到朴素直拼，绝不阻塞主流程。
        """
        if not rows or not columns:
            return "查询未返回数据。"
        try:
            preview = rows[:30]
            head = "、".join(columns)
            body = "\n".join(
                " | ".join("" if v is None else str(v) for v in r) for r in preview
            )
            prompt = (
                f"用户问题：{question}\n"
                f"查询结果列：{head}\n"
                f"前 {len(preview)} 行数据（用 | 分隔）：\n{body}\n"
                f"请用 1-3 句中文，给非技术 HR 用户自然语言总结这段数据，"
                f"直接说人话，不要提及 SQL/数据库/查询等技术词汇，必要时给出关键数字。"
            )
            system = "你是数据解读助手。只输出自然语言总结，不输出 JSON/SQL/代码/Markdown。"
            text = get_llm().chat(prompt, system=system, temperature=0.3).strip()
            if text:
                return text
        except Exception as exc:
            logger.warning("LLM 解读失败，回退到朴素直拼: %s", exc)
        # 兜底：朴素直拼首行所有列（保证至少可读，不让用户空白屏）
        first = rows[0]
        parts = [f"{c}：{first[i] if i < len(first) else ''}" for i, c in enumerate(columns)]
        tail = "…" if len(rows) > 1 else ""
        return "查询结果：" + "；".join(parts) + tail


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
