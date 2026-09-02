"""AI 助手对话接口（J07 移动端入口 · AI-6）。

只在小程序端使用（管理端不显示问数入口）：
    - 问数类（统计/多少/人数/分布…）→ Agent⑤ NL2SQL 引擎（D-3）出图
    - 其他（人才问答/查档案…）→ RAG 问答（人才库检索 + LLM 总结）
每次对话写入 ai_conversation 表（type=nl2sql/rag），支持历史追溯。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.db.session import SessionLocal
from app.utils.response import BusinessError, ok

router = APIRouter()

# 问数意图关键词（命中走 NL2SQL 引擎）
_QUERY_KEYWORDS = ("统计", "多少", "人数", "分布", "占比", "排行", "数量", "比例", "趋势", "平均", "几个", "几名", "查一下", "总数")


class ChatRequest(BaseModel):
    message: str
    chart_type: str = "bar"


def _is_query(message: str) -> bool:
    return any(k in message for k in _QUERY_KEYWORDS)


@router.post("/chat")
async def chat(body: ChatRequest, user=Depends(get_current_user)):
    """对话入口：按意图分流 NL2SQL / RAG，返回回答文本 + 可选图表配置。"""
    message = (body.message or "").strip()
    if not message:
        raise BusinessError(400, "消息不能为空")

    result: dict[str, Any] = {}
    if _is_query(message):
        # ---- 问数：Agent⑤ NL2SQL ----
        from app.ai.agents import query_agent
        out = await query_agent.run({"question": message, "chart_type": body.chart_type})
        if out.get("status") != "done":
            result = {"type": "nl2sql", "answer": f"问数未完成：{out.get('error_msg') or '请换个问法'}", "chart_json": None}
        else:
            rows = out.get("rows") or []
            cols = out.get("columns") or []
            text_parts = [f"{c}：{r}" for c, r in zip(cols, rows[0])] if rows and cols else []
            answer = "查询结果：\n" + "\n".join(text_parts) if text_parts else f"共 {len(rows)} 行数据"
            result = {"type": "nl2sql", "answer": answer, "chart_json": out.get("chart_json")}
    else:
        # ---- 人才问答：RAG ----
        from app.services.talent_service import rag_ask
        with SessionLocal() as db:
            try:
                resp = rag_ask(db, message, top_k=5)
                result = {"type": "rag", "answer": resp.answer, "chart_json": None,
                          "talents_covered": resp.talents_covered}
            except BusinessError as e:
                result = {"type": "rag", "answer": f"（知识库暂未覆盖该问题：{e.message}）", "chart_json": None}

    # 写入对话记录（ai_conversation）
    try:
        import json
        with SessionLocal() as db:
            db.execute(
                "INSERT INTO ai_conversation (user_id, type, question, answer, chart_json, created_at)"
                " VALUES (%s, %s, %s, %s, %s, NOW())",
                (user.id, result["type"], message, result["answer"],
                 json.dumps(result.get("chart_json"), ensure_ascii=False) if result.get("chart_json") else None),
            )
            db.commit()
    except Exception:  # noqa: BLE001  记录失败不阻塞回复
        pass

    return ok({
        "message": message,
        "answer": result.get("answer"),
        "chart_json": result.get("chart_json"),
        "type": result.get("type"),
    })
