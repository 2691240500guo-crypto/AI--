"""硅基流动 OpenAI 兼容接口客户端。"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.core.config import get_settings


class SiliconFlowClient:
    """面向结构化 Agent 输出的轻量客户端。"""

    def chat_json(self, prompt: str, *, system: str) -> dict[str, Any]:
        settings = get_settings()
        if not settings.SILICONFLOW_API_KEY:
            raise RuntimeError("未配置硅基流动 API Key")

        url = f"{settings.SILICONFLOW_BASE_URL.rstrip('/')}/chat/completions"
        try:
            response = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.SILICONFLOW_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.SILICONFLOW_MODEL,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "stream": False,
                },
                timeout=settings.SILICONFLOW_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return self._parse_json(content)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise RuntimeError(f"硅基流动调用或返回结果无效：{exc}") from exc

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        value = json.loads(cleaned)
        if not isinstance(value, dict):
            raise ValueError("模型返回结果不是 JSON 对象")
        return value
