"""Agent④ 培训计划生成器。"""

from __future__ import annotations

import json
from typing import Any

from app.agents.siliconflow_client import SiliconFlowClient
from app.core.config import get_settings


class TrainingAgent:
    """根据测评短板生成结构化培训计划，培训模块不可用时仍可本地运行。"""

    @staticmethod
    def build_local_plan(weak_dimensions: list[str]) -> dict[str, Any]:
        dimensions = weak_dimensions or ["综合能力"]
        return {
            "version": "1.0",
            "source": "local",
            "title": "测评短板提升计划",
            "objectives": [f"提升{dimension}能力" for dimension in dimensions],
            "courses": [
                {
                    "dimension": dimension,
                    "title": f"{dimension}专项训练",
                    "priority": "high" if index == 0 else "medium",
                    "reason": f"测评识别到{dimension}需要提升",
                }
                for index, dimension in enumerate(dimensions)
            ],
            "milestones": ["完成专项学习", "完成练习与复盘", "参加针对性复测"],
        }

    @staticmethod
    def generate(weak_dimensions: list[str], context: dict[str, Any] | None = None) -> dict[str, Any]:
        local_plan = TrainingAgent.build_local_plan(weak_dimensions)
        settings = get_settings()
        if settings.ASSESSMENT_REPORT_MODE.lower() == "local":
            raise RuntimeError("当前报告模式为 local")

        prompt = (
            "你是企业培训规划助手。请根据测评短板和业务上下文生成培训计划，"
            "只返回 JSON，不要 Markdown。必须包含 title、objectives、courses、milestones。"
            "courses 必须是对象数组，每项包含 dimension、title、priority、reason。"
            f"\n测评短板：{json.dumps(weak_dimensions, ensure_ascii=False)}"
            f"\n业务上下文：{json.dumps(context or {}, ensure_ascii=False)}"
        )
        plan = SiliconFlowClient().chat_json(
            prompt,
            system="你输出的是企业培训计划 JSON，禁止输出额外解释文字。",
        )
        TrainingAgent.validate(plan)
        plan["version"] = "1.0"
        plan["source"] = "siliconflow"
        return plan

    @staticmethod
    def validate(plan: dict[str, Any]) -> None:
        for key in ("title", "objectives", "courses", "milestones"):
            if key not in plan:
                raise ValueError(f"培训计划缺少字段：{key}")
        if not isinstance(plan["title"], str) or any(
            not isinstance(plan[key], list) for key in ("objectives", "courses", "milestones")
        ):
            raise ValueError("培训计划字段格式无效")
        if any(not isinstance(item, str) for key in ("objectives", "milestones") for item in plan[key]):
            raise ValueError("培训计划目标或里程碑格式无效")
        for course in plan["courses"]:
            if not isinstance(course, dict) or any(
                not isinstance(course.get(key), str)
                for key in ("dimension", "title", "priority", "reason")
            ):
                raise ValueError("培训计划课程格式无效")
