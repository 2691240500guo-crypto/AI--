"""Agent④ 培训推送（P8/P9）。契约见 docs/07-Agent接口契约.md。

统一入口 async def run(input_data) -> dict：
    入参 input_data: {"talent_id": int, "shortcomings": [str]?, "position_ids": [int]?}
    返回: {"plan_id": int, "course_ids": [int], "status": "done"|"failed"}

v2 增强：
- shortcomings 可省略：内部自动从 tal_talent_report.summary_report 提取短板。
- position_ids 可省略：内部自动从 match_result 取适配岗位并总结岗位说明书。
内部复用 TrainingAgentService。
"""
from typing import Any

from app.utils.logger import logger


async def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """契约：in {talent_id, shortcomings[]?, position_ids[]?} → out {plan_id, course_ids[], status}。"""
    try:
        talent_id: int = int(input_data["talent_id"])
        shortcomings: list[str] | None = input_data.get("shortcomings") or None
        position_ids: list[int] | None = input_data.get("position_ids") or None

        from app.db.session import SessionLocal
        from app.services.training_agent import TrainingAgentService

        with SessionLocal() as db:
            result = TrainingAgentService.generate_plan(
                db, talent_id=talent_id, shortage_tags=shortcomings,
                position_ids=position_ids)
            db.commit()
            return {
                "plan_id": result["plan_id"],
                "course_ids": result["course_ids"],
                "shortage_tags": result.get("shortage_tags", []),
                "position_tags": result.get("position_tags", []),
                "status": "done",
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent④ 培训推送失败: %s", exc)
        return {"status": "failed", "error_msg": str(exc)}
