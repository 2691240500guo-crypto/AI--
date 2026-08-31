"""大模型客户端（Ollama）。

统一封装 Ollama 的调用入口，团队成员只需持有本类，无需关心底层 HTTP 细节。
依赖在模块内惰性导入：未安装 ollama 库时不影响其它模块初始化。
"""
from __future__ import annotations

from typing import Any

from app.core.config import get_settings


class LLMClient:
    """Ollama 大模型客户端。

    用法：
        from app.utils.llm import get_llm

        llm = get_llm()
        text = llm.chat("你好")
        embedding = llm.embed("人才简介文本")
    """

    def __init__(self) -> None:
        from ollama import Client  # 惰性导入，避免依赖未安装导致启动失败

        settings = get_settings()
        self._client = Client(host=settings.OLLAMA_BASE_URL, timeout=settings.OLLAMA_TIMEOUT)
        self.model = settings.OLLAMA_MODEL
        self.embed_model = settings.OLLAMA_EMBED_MODEL

    def chat(self, prompt: str, system: str | None = None, *, model: str | None = None,
             temperature: float = 0.7) -> str:
        """对话补全，返回纯文本回答。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = self._client.chat(model=model or self.model, messages=messages,
                                 options={"temperature": temperature})
        return resp["message"]["content"]

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        """文本向量化，返回 N 维向量列表。"""
        resp = self._client.embed(model=model or self.embed_model, input=text)
        return resp["embeddings"][0]

    def list_models(self) -> list[dict[str, Any]]:
        """列出本机已安装的模型列表。"""
        return self._client.list()["models"]


_llm: LLMClient | None = None


def get_llm() -> LLMClient:
    """获取全局单例的 LLM 客户端（懒初始化）。"""
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm
