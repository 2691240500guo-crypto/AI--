"""LangGraph 协同图（AI-5）。P1 编排层：串联 Agent①-⑤，承载三大闭环。

设计依据：docs/07-Agent接口契约.md（State 定义 + Agent 输入输出）。

机制：
    - State = 全局共享数据包，所有节点读它、写它
    - 节点 = 一个 Agent / 业务步骤，签名 async def node(state) -> dict（返回要更新的字段）
    - 边 = 顺序边（无条件）/ 条件边（路由函数决定走向，支持循环）

节点已接入真实 Agent（统一走 app.ai.agents 契约入口）：
    parse    → resume_agent.run（Agent① 简历解析；无 file_url 时透传）
    assess   → 业务节点：校验在线测评已交卷（A-3/4）
    report   → assess_agent.run（Agent② 测评分析，产出 shortcomings）
    training → train_agent.run（Agent④ 培训推送，短板→计划）
    retest   → 业务节点：复测计数（上限 3 防死循环）
    match    → MatchAgent.reverse_match（Agent③ 岗位匹配，人岗闭环）
    query    → query_agent.run（Agent⑤ NL2SQL，问数闭环）

入口分流（route_entry）：question → 问数⑤；position_ids → 人岗①→③；否则成长②→④。

依赖：langgraph>=0.2（见 requirements.txt）。
"""
from typing import TypedDict

from langgraph.graph import END, StateGraph

# ---------------------------------------------------------------------------
# 1. 全局状态（契约第 4 节）——节点之间传的就是这个
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    # 通用
    agent_code: str            # 当前执行节点代号（任务落库 ai_agent_task 用）
    error: str | None
    # 闭环 A 成长（① 简历 → ② 测评分析 → ④ 培训 → 复测）
    file_url: str              # Agent① 输入：简历文件地址（minio:// 或 http(s)://）
    file_type: str             # Agent① 输入：pdf|word|image
    filename: str | None
    tags: list[str]            # Agent① 产物
    talent_id: int
    result_id: int | None      # 在线测评结果（业务节点 assess 校验）
    report: dict | None        # Agent② 产物（雷达/建议）
    level: str | None          # 档案等级（Agent② 回写；优秀/良好≈S/A）
    shortcomings: list[str]    # ② 输出 → ④ 输入（接力命门）
    plan_id: int | None        # Agent④ 产物
    course_ids: list[int]      # Agent④ 产物
    retest_count: int          # 复测次数（上限 3，防死循环）
    # 闭环 B 人岗（①→③）
    position_ids: list[int]
    matches: list[dict]        # Agent③ 产物
    # 闭环 C 问数（⑤）
    question: str
    answer: dict               # Agent⑤ 产物


# ---------------------------------------------------------------------------
# 2. 节点（真实 Agent，统一走 app.ai.agents 契约入口）
# ---------------------------------------------------------------------------
async def node_parse(state: AgentState) -> dict:
    """Agent① 简历解析：下载 → 结构化 → 落库 → 打标签 → 向量。

    无 file_url 时透传（人岗闭环/问数闭环入口不需要简历解析）。
    """
    file_url = state.get("file_url")
    if not file_url:
        return {"agent_code": "resume", "error": None}
    from app.ai.agents import resume_agent
    out = await resume_agent.run({
        "file_url": file_url,
        "file_type": state.get("file_type") or "pdf",
        "filename": state.get("filename"),
    })
    if out.get("status") != "done":
        return {"agent_code": "resume", "error": out.get("error_msg") or "简历解析失败"}
    return {"agent_code": "resume", "talent_id": out.get("talent_id"),
            "tags": out.get("tags", []), "error": None}


async def node_assess(state: AgentState) -> dict:
    """业务节点：在线测评/判分（A-3/4）——校验 result_id 存在且已交卷。"""
    result_id = state.get("result_id")
    if not result_id:
        return {"agent_code": "assess", "error": "缺少 result_id（需先完成在线测评）"}
    from app.db.session import SessionLocal
    from app.models.assessment import AssessmentResult
    with SessionLocal() as db:
        r = db.get(AssessmentResult, int(result_id))
        if r is None:
            return {"agent_code": "assess", "error": f"测评结果不存在: {result_id}"}
        if r.status not in (2, 3):
            return {"agent_code": "assess", "error": f"测评未完成（status={r.status}），需先交卷/判分"}
        talent_id = r.talent_id
    return {"agent_code": "assess", "talent_id": talent_id,
            "result_id": int(result_id), "error": None}


async def node_report(state: AgentState) -> dict:
    """Agent② 测评分析：报告 + 短板（shortcomings 是 Agent④ 接力命门）。"""
    if state.get("error"):
        return {"agent_code": "assess_report", "error": state["error"]}
    from app.ai.agents import assess_agent
    out = await assess_agent.run({
        "talent_id": state.get("talent_id"),
        "result_id": state.get("result_id"),
    })
    if out.get("status") != "done":
        return {"agent_code": "assess_report", "error": out.get("error_msg") or "测评分析失败"}
    return {"agent_code": "assess_report", "report": out.get("report"),
            "level": out.get("level"), "shortcomings": out.get("shortcomings", []),
            "error": None}


async def node_training(state: AgentState) -> dict:
    """Agent④ 培训推送：短板 → 选课 → 建计划 → 消息推送。"""
    if state.get("error"):
        return {"agent_code": "train", "error": state["error"]}
    from app.ai.agents import train_agent
    out = await train_agent.run({
        "talent_id": state.get("talent_id"),
        "shortcomings": state.get("shortcomings", []),
    })
    if out.get("status") != "done":
        return {"agent_code": "train", "error": out.get("error_msg") or "培训推送失败"}
    return {"agent_code": "train", "plan_id": out.get("plan_id"),
            "course_ids": out.get("course_ids", []), "error": None}


async def node_retest(state: AgentState) -> dict:
    """复测判定（业务节点）：计数 +1，等待二次测评（新 result_id 由调用方传入）。"""
    return {"agent_code": "retest", "retest_count": (state.get("retest_count") or 0) + 1}


async def node_match(state: AgentState) -> dict:
    """Agent③ 岗位匹配（人岗闭环 ①→③）：人才 → 岗位向量检索 + 加权打分。

    复用 P6/P7 的 MatchAgent.reverse_match（人才画像向量 → position_vec 召回 → 打分）。
    """
    if state.get("error"):
        return {"agent_code": "match", "error": state["error"]}
    talent_id = state.get("talent_id")
    if not talent_id:
        return {"agent_code": "match", "error": "缺少 talent_id（需先有人才档案）"}
    from app.ai.agents.match_agent import MatchAgent
    from app.db.session import SessionLocal
    position_ids = state.get("position_ids") or []
    top_k = max(len(position_ids), 5) if position_ids else 5
    with SessionLocal() as db:
        try:
            results = MatchAgent.reverse_match(db, talent_id, top_k=top_k)
            if position_ids:
                results = [r for r in results if r["position_id"] in position_ids]
        except Exception as exc:  # noqa: BLE001
            return {"agent_code": "match", "error": f"岗位匹配失败: {exc}"}
    return {"agent_code": "match", "matches": results, "error": None}


async def node_query(state: AgentState) -> dict:
    """Agent⑤ NL2SQL（问数闭环 ⑤）：自然语言 → SQL → 只读执行 → 图表。"""
    if state.get("error"):
        return {"agent_code": "query", "error": state["error"]}
    question = state.get("question")
    if not question:
        return {"agent_code": "query", "error": "缺少 question"}
    from app.ai.agents import query_agent
    out = await query_agent.run({
        "question": question,
        "chart_type": state.get("chart_type") or "bar",
    })
    if out.get("status") != "done":
        return {"agent_code": "query", "error": out.get("error_msg") or "问数失败"}
    return {"agent_code": "query", "answer": out, "error": None}


# ---------------------------------------------------------------------------
# 3. 条件边（路由函数：返回目标分支名）
# ---------------------------------------------------------------------------
def route_entry(state: AgentState) -> str:
    """入口分流（三大闭环）：有 question → 问数⑤；有 position_ids → 人岗①→③；否则成长②→④。"""
    if state.get("question"):
        return "query"
    if state.get("position_ids"):
        return "match"
    return "assess"


def route_report(state: AgentState) -> str:
    """报告完成后（A-7 联动）：存在短板 → 培训；无短板 → 结束。"""
    return "training" if state.get("shortcomings") else "end"


def route_retest(state: AgentState) -> str:
    """复测后：S/A 级（优秀/良好）达标 → 结束；未达标且未超 3 次 → 重新测评；超次数 → 结束。"""
    level = state.get("level")
    if level in ("S", "A", "优秀", "良好"):
        return "end"
    return "retry" if (state.get("retest_count") or 0) < 3 else "end"


# ---------------------------------------------------------------------------
# 4. 建图 + 编译（支持测试时覆盖节点）
# ---------------------------------------------------------------------------
_DEFAULT_NODES = {
    "parse": node_parse,
    "assess": node_assess,
    "report": node_report,
    "training": node_training,
    "retest": node_retest,
    "match": node_match,
    "query": node_query,
}


def build_graph(overrides: dict | None = None):
    """构造并编译协同图。overrides 用于测试/演示时替换节点。"""
    nodes = dict(_DEFAULT_NODES)
    if overrides:
        nodes.update(overrides)

    g = StateGraph(AgentState)
    for name, fn in nodes.items():
        g.add_node(name, fn)

    # 入口分流：问数⑤ / 人岗①→③ / 成长②→④
    g.set_entry_point("parse")
    g.add_conditional_edges("parse", route_entry,
                            {"assess": "assess", "match": "match", "query": "query"})
    g.add_edge("query", END)
    g.add_edge("match", END)

    # 链路 A 成长闭环：档案 → 测评 → 报告 →（短板）培训 → 复测 →（不合格循环）
    g.add_edge("assess", "report")
    g.add_conditional_edges("report", route_report, {"training": "training", "end": END})
    g.add_edge("training", "retest")
    g.add_conditional_edges("retest", route_retest, {"retry": "assess", "end": END})
    return g.compile()


# 默认实例（真实 Agent 已接入）
graph_app = build_graph()
