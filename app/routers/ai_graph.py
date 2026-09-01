"""LangGraph 协同图对外接口（AI-5）——三大闭环的统一 HTTP 入口。

用途：把 app/ai/graph.py 的协同图暴露给前端/小程序/测试，按入参自动分流：
    - 成长闭环（②→④）：传 file_url（简历入口）或 result_id+talent_id（测评入口）
    - 人岗闭环（①→③）：传 talent_id + position_ids
    - 问数闭环（⑤）：传 question
返回最终 AgentState（含闭环类型标识，便于前端/测试判断流转结果）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.utils.response import BusinessError, ok

router = APIRouter()


class GraphRunRequest(BaseModel):
    # ---- 成长闭环（②→④）----
    file_url: str | None = None      # 简历入口（minio:// 或 http(s)://）
    file_type: str = "pdf"           # pdf|word|image
    filename: str | None = None
    result_id: int | None = None     # 测评入口（已完成测评结果 id）
    talent_id: int | None = None     # 人才 id（成长/人岗共用）
    # ---- 人岗闭环（①→③）----
    position_ids: list[int] | None = None
    # ---- 问数闭环（⑤）----
    question: str | None = None
    chart_type: str = "bar"


@router.post("/run")
async def run_graph(body: GraphRunRequest, user=Depends(get_current_user)):
    """触发 LangGraph 协同图，按入参自动分流到对应闭环，返回最终 AgentState。"""
    from app.ai.graph import graph_app

    if not any((body.file_url, body.result_id, body.position_ids, body.question)):
        raise BusinessError(400, "缺少触发参数：需传 file_url / result_id / position_ids / question 之一")

    state: dict[str, Any] = {}
    if body.file_url:
        state.update(file_url=body.file_url, file_type=body.file_type)
        if body.filename:
            state["filename"] = body.filename
    if body.talent_id:
        state["talent_id"] = body.talent_id
    if body.result_id:
        state["result_id"] = body.result_id
    if body.position_ids:
        state["position_ids"] = body.position_ids
    if body.question:
        state.update(question=body.question, chart_type=body.chart_type)

    result: dict[str, Any] = await graph_app.ainvoke(state)

    # 闭环类型识别（供前端/测试判断流转结果）
    closed_loop = (
        "growth" if result.get("plan_id") is not None else
        "match" if result.get("matches") else
        "query" if result.get("answer") else "unknown"
    )
    return ok({
        "closed_loop": closed_loop,
        "state": {
            k: result.get(k) for k in (
                "agent_code", "error", "talent_id", "tags", "result_id",
                "report", "level", "shortcomings", "plan_id", "course_ids",
                "retest_count", "matches", "answer",
            )
        },
    })
