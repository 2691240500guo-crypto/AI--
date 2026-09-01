"""Dify 编排客户端。

封装 Dify Workflow 应用的调用入口。Dify 负责多 Agent 编排（第八章），
后端在 DIFY_ENABLED=True 时优先走 Dify，失败/未启用时降级到直连 LLM。

用法：
    from app.utils.dify_client import get_dify
    dify = get_dify()
    if dify.available:
        outputs = dify.run_workflow({"talent_name": "...", "score": 10, ...})
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

from app.core.config import get_settings


class DifyClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_key = s.DIFY_API_KEY
        self.base_url = s.DIFY_BASE_URL.rstrip("/")
        self.timeout = s.DIFY_TIME_OUT
        self.enabled = bool(s.DIFY_ENABLED) and bool(self.api_key)

    @property
    def available(self) -> bool:
        return self.enabled

    def run_workflow(self, inputs: dict, user: str = "admin") -> dict:
        """调用 Workflow 应用（blocking 模式），返回 outputs 字典。"""
        if not self.available:
            raise RuntimeError("Dify 未启用（DIFY_ENABLED 或 DIFY_API_KEY 未配置）")
        payload = {
            "inputs": inputs,
            "response_mode": "blocking",
            "user": user,
        }
        req = Request(f"{self.base_url}/v1/workflows/run",
                      data=json.dumps(payload).encode("utf-8"), method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        with urlopen(req, timeout=self.timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        data = body.get("data") or {}
        status = data.get("status")
        if status not in (None, "succeeded", "success"):
            err = data.get("error") or data.get("errors") or body
            raise RuntimeError(f"Dify workflow 执行失败：{err}")
        return data.get("outputs") or {}


_dify: DifyClient | None = None


def get_dify() -> DifyClient:
    """获取全局单例 Dify 客户端。"""
    global _dify
    if _dify is None:
        _dify = DifyClient()
    return _dify
