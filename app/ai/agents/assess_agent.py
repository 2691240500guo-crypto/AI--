"""Agent② 测评分析（契约见 docs/07-Agent接口契约.md 第 62-76 行）。

统一入口：async def run(input_data) -> dict
    入参: {"talent_id": int, "result_id": int}
    返回: {"report": {...}, "level": str, "shortcomings": [str], "status": "done"|"failed"}

内部流程（复用 C 域报告管线）：
    读成绩 asm_result → 生成报告（本地规则版 build_local_report；
    配置 ASSESSMENT_REPORT_MODE=llm 时由 AssessmentAgent 增强）→ 写 asm_result.report_json
    → 回写 tal_talent.level → shortcomings（字符串数组）交 Agent④ 接力。
"""
from __future__ import annotations

import asyncio
from typing import Any

from app.utils.logger import logger


async def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """契约：in {talent_id, result_id} → out {report, level, shortcomings, status}。"""
    try:
        talent_id: int = int(input_data["talent_id"])
        result_id: int = int(input_data["result_id"])

        from app.db.session import SessionLocal
        from app.models.assessment import AssessmentResult
        from app.services.assessment_report_service import AssessmentReportService

        with SessionLocal() as db:
            result = db.get(AssessmentResult, result_id)
            if result is None:
                return {"status": "failed", "error_msg": f"测评结果不存在: {result_id}"}
            if result.talent_id != talent_id:
                return {"status": "failed", "error_msg": "talent_id 与测评结果不匹配"}

            # 生成报告（内部：local 规则版 + 可选 LLM 增强 + 落 report_json + 回写 level）
            report = AssessmentReportService.generate(db, result)
            db.commit()
            db.refresh(result)

            # 契约口径：level 输出字母 S/A/B/C（映射 优秀=S/良好=A/合格=B/待提升=C）
            # report.rating 保留 C 域中文原值（前端展示用）
            rating = report.get("rating") or "C"
            level = _cn_to_level(str(rating))
            shortcomings = [str(w) for w in report.get("weaknesses", [])]
            return {
                "report": report,
                "level": level,
                "shortcomings": shortcomings,
                "status": "done",
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent② 测评分析失败: %s", exc)
        return {"status": "failed", "error_msg": str(exc)}


# 契约等级映射：C 域中文 rating → 契约字母 S/A/B/C（graph 复测路由依赖）
_LEVEL_MAP = {"优秀": "S", "良好": "A", "合格": "B", "待提升": "C"}


def _cn_to_level(rating: str) -> str:
    """中文等级 → 契约字母；已是字母原样返回。"""
    return _LEVEL_MAP.get(rating, rating if rating in ("S", "A", "B", "C") else "C")
