"""大模型客户端（Ollama / 硅基流动 SiliconFlow）。

统一封装 chat 与 embed 入口，团队成员只需持有本类，无需关心底层 HTTP 细节。
- embed：默认走硅基流动（SILICON_FLOW_EMBED_MODEL，云端 1024 维 bge-m3）
- chat：按 LLM_STRATEGY 切换 ollama / silicon_flow
依赖在模块内惰性导入：未安装 ollama 库时不影响其它模块初始化。
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.core.config import get_settings


class LLMClient:
    """大模型客户端。

    用法：
        from app.utils.llm import get_llm

        llm = get_llm()
        text = llm.chat("你好")
        embedding = llm.embed("人才简介文本")
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.strategy = settings.LLM_STRATEGY
        self.model = settings.OLLAMA_MODEL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        # 硅基流动配置（key 兼容两套命名，.env 填 SILICON_FLOW_API_KEY 或 SILICONFLOW_API_KEY 任一即可）
        self.sf_api_key = settings.SILICON_FLOW_API_KEY or settings.SILICONFLOW_API_KEY
        self.sf_base = settings.SILICON_FLOW_BASE_URL or settings.SILICONFLOW_BASE_URL
        self.sf_llm_model = settings.SILICON_FLOW_LLM_MODEL or settings.SILICONFLOW_MODEL
        self.sf_embed_model = settings.SILICON_FLOW_EMBED_MODEL
        # Ollama 客户端（惰性，仅当 strategy=ollama 且需要时创建）
        self._ollama: Any | None = None

    # ==================== 硅基流动（OpenAI 兼容） ====================

    def _sf_request(self, path: str, payload: dict) -> dict:
        """调用硅基流动 OpenAI 兼容接口。"""
        req = urllib.request.Request(
            f"{self.sf_base}/{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.sf_api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            settings = get_settings()
            timeout = max(1, int(getattr(settings, "ASSESSMENT_AI_TIMEOUT", 20)))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"硅基流动接口 {path} 失败 HTTP {e.code}: {detail}") from e

    def _sf_embed(self, text: str, model: str | None = None) -> list[float]:
        data = self._sf_request("embeddings", {"model": model or self.sf_embed_model, "input": text})
        return data["data"][0]["embedding"]

    def _sf_chat(self, prompt: str, system: str | None, model: str | None,
                 temperature: float) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        data = self._sf_request("chat/completions", {
            "model": model or self.sf_llm_model,
            "messages": messages,
            "temperature": temperature,
        })
        return data["choices"][0]["message"]["content"]

    # ==================== Ollama ====================

    def _get_ollama(self) -> Any:
        if self._ollama is None:
            from ollama import Client  # 惰性导入

            settings = get_settings()
            self._ollama = Client(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_TIMEOUT)
        return self._ollama

    def _ollama_embed(self, text: str, model: str | None = None) -> list[float]:
        resp = self._get_ollama().embed(model=model or self.embed_model, input=text)
        return resp["embeddings"][0]

    def _ollama_chat(self, prompt: str, system: str | None, model: str | None,
                     temperature: float) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._get_ollama().chat(
            model=model or self.model, messages=messages,
            options={"temperature": temperature},
        )
        return resp["message"]["content"]

    # ==================== 对外接口 ====================

    def chat(self, prompt: str, system: str | None = None, *, model: str | None = None,
             temperature: float = 0.7) -> str:
        """对话补全，返回纯文本回答（按 LLM_STRATEGY 选择后端）。"""
        if self.strategy == "silicon_flow":
            return self._sf_chat(prompt, system, model, temperature)
        return self._ollama_chat(prompt, system, model, temperature)

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        """文本向量化，返回 N 维向量列表（默认走硅基流动 bge-m3）。"""
        if self.strategy == "silicon_flow" or self.sf_api_key:
            return self._sf_embed(text, model)
        return self._ollama_embed(text, model)

    def list_models(self) -> list[dict[str, Any]]:
        """列出模型列表（当前仅 Ollama 支持）。"""
        return self._get_ollama().list()["models"]


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    """获取全局单例的 LLM 客户端（懒初始化）。"""
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
