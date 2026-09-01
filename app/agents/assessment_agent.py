"""Agent② 测评分析适配层，使用硅基流动生成结构化报告。"""

from __future__ import annotations

import json
from typing import Any

from app.agents.siliconflow_client import SiliconFlowClient
from app.core.config import get_settings


class AssessmentAgent:
    """硅基流动报告分析器，不参与核心判分。"""

    REQUIRED_FIELDS = ("rating", "strengths", "weaknesses", "recommendations")

    @staticmethod
    def enhance(local_report: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        settings = get_settings()
        if settings.ASSESSMENT_REPORT_MODE.lower() == "local":
            raise RuntimeError("当前报告模式为 local")

        prompt = (
            "你是企业人才测评分析助手。请根据测评基础结果和业务上下文生成分析结果，"
            "只返回 JSON，不要 Markdown。必须包含 rating、strengths、weaknesses、"
            "recommendations 四个字段，字段值分别为字符串或字符串数组。"
            f"\n测评基础结果：{json.dumps(local_report, ensure_ascii=False)}"
            f"\n业务上下文：{json.dumps(context or {}, ensure_ascii=False)}"
        )
        enhanced = SiliconFlowClient().chat_json(
            prompt,
            system="你输出的是企业测评报告 JSON，禁止输出额外解释文字。",
        )
        AssessmentAgent.validate(enhanced)
        return enhanced

    @classmethod
    def validate(cls, report: dict[str, Any]) -> None:
        for key in cls.REQUIRED_FIELDS:
            if key not in report:
                raise ValueError(f"AI 报告缺少字段：{key}")
        if (
            not isinstance(report["rating"], str)
            or any(not isinstance(report[key], list) for key in cls.REQUIRED_FIELDS[1:])
            or any(
                not isinstance(item, str)
                for key in cls.REQUIRED_FIELDS[1:]
                for item in report[key]
            )
        ):
            raise ValueError("AI 报告字段格式无效")
