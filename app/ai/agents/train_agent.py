"""Agent④ 培训推送（P8/P9）。契约见 docs/07-Agent接口契约.md。

统一入口 async def run(input_data) -> dict：
    入参 input_data: {"talent_id": int, "shortcomings": [str], "position_ids": [int]?}
    返回: {"plan_id": int, "course_ids": [int], "status": "done"|"failed"}
内部复用 TrainingAgentService（选课→建计划→消息推送）。
岗位能力 position_ids 为预留可选参数，M 域岗位画像完成后接入。
"""
from typing import Any

from app.utils.logger import logger


async def run(input_data: dict[str, Any]) -> dict[str, Any]:
    """契约：in {talent_id, shortcomings[]} → out {plan_id, course_ids[], status}。"""
    try:
        talent_id: int = input_data["talent_id"]
        shortcomings: list[str] = input_data.get("shortcomings", [])
        # 岗位能力预留：M 域 D02 完成后，从岗位画像解析能力要求并传入选课逻辑
        # position_ids: list[int] = input_data.get("position_ids", [])

        from app.db.session import SessionLocal
        from app.services.training_agent import TrainingAgentService

        with SessionLocal() as db:
            result = TrainingAgentService.generate_plan(
                db, talent_id=talent_id, shortage_tags=shortcomings)
            db.commit()
            return {
                "plan_id": result["plan_id"],
                "course_ids": result["course_ids"],
                "status": "done",
            }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent④ 培训推送失败: %s", exc)
        return {"status": "failed", "error_msg": str(exc)}
