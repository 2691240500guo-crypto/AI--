"""LangGraph 协同图（AI-5）。P1 编排层：串联 Agent①-⑤，承载三大闭环。

设计依据：docs/07-Agent接口契约.md（State 定义 + Agent 输入输出）。

机制：
    - State = 全局共享数据包，所有节点读它、写它
    - 节点 = 一个 Agent / 业务步骤，签名 async def node(state) -> dict（返回要更新的字段）
    - 边 = 顺序边（无条件）/ 条件边（路由函数决定走向，支持循环）

当前状态：节点为占位（stub），明日按 07-契约 逐个替换为真实 Agent。
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
    # 闭环 A 成长（②→④）
    talent_id: int
    result_id: int | None
    report: dict | None        # Agent② 产物（雷达/建议）
    level: str | None          # 档案等级 S/A/B/C（Agent② 回写）
    shortcomings: list[str]    # ② 输出 → ④ 输入（接力命门）
    plan_id: int | None        # Agent④ 产物
    retest_count: int          # 复测次数（上限 3，防死循环）
    # 闭环 B 人岗（①→③）
    position_ids: list[int]
    matches: list[dict]        # Agent③ 产物
    # 闭环 C 问数（⑤）
    question: str
    answer: dict               # Agent⑤ 产物


# ---------------------------------------------------------------------------
# 2. 节点（占位版；明日按 07-契约 替换为真实 Agent）
# ---------------------------------------------------------------------------
async def node_parse(state: AgentState) -> dict:
    """Agent① 简历解析。TODO(P2/P3): 接入 resume_agent.run"""
    return {"agent_code": "resume"}


async def node_assess(state: AgentState) -> dict:
    """在线测评/判分（业务节点，非 Agent）。TODO(P4): 接测评域"""
    return {"agent_code": "assess"}


async def node_report(state: AgentState) -> dict:
    """Agent② 测评分析。TODO(P4/P5): 接入 assess_agent.run"""
    return {"agent_code": "assess_report"}


async def node_training(state: AgentState) -> dict:
    """Agent④ 培训推送。TODO(P8/P9): 接入 train_agent.run"""
    return {"agent_code": "train"}


async def node_retest(state: AgentState) -> dict:
    """复测判定（业务节点）。TODO(P4): 接测评域二次测评"""
    return {"agent_code": "retest"}


# ---------------------------------------------------------------------------
# 3. 条件边（路由函数：返回目标分支名）
# ---------------------------------------------------------------------------
def route_report(state: AgentState) -> str:
    """报告完成后（A-7 联动）：存在短板 → 培训；无短板 → 结束。"""
    return "training" if state.get("shortcomings") else "end"


def route_retest(state: AgentState) -> str:
    """复测后：S/A 级达标 → 结束；未达标且未超 3 次 → 重新测评；超次数 → 结束。"""
    if state.get("level") in ("S", "A"):
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
}


def build_graph(overrides: dict | None = None):
    """构造并编译协同图。overrides 用于测试/演示时替换节点。"""
    nodes = dict(_DEFAULT_NODES)
    if overrides:
        nodes.update(overrides)

    g = StateGraph(AgentState)
    for name, fn in nodes.items():
        g.add_node(name, fn)

    # 链路 A 成长闭环：档案 → 测评 → 报告 →（短板）培训 → 复测 →（不合格循环）
    g.set_entry_point("parse")
    g.add_edge("parse", "assess")
    g.add_edge("assess", "report")
    g.add_conditional_edges("report", route_report, {"training": "training", "end": END})
    g.add_edge("training", "retest")
    g.add_conditional_edges("retest", route_retest, {"retry": "assess", "end": END})
    return g.compile()


# 默认实例（真实节点就绪后直接换掉 _DEFAULT_NODES 即可）
graph_app = build_graph()
