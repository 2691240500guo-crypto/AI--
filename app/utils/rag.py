"""RAG 检索增强生成工具。

将 LLM（Ollama）与向量库（Milvus）组合成最简 RAG 链路：
文档切块 → 向量化 → 入库；查询 → 召回 → 拼 prompt → 生成。
不依赖 langchain，使用本项目自带的 llm / vector_store 工具，保持依赖最小。
"""
from __future__ import annotations

from app.utils.llm import get_llm
from app.utils.vector_store import get_vector_store


def _split_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """简单按字符长度切块，块间保留 overlap 避免语义断裂。"""
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += step
    return chunks


class RAGTool:
    """最简 RAG 工具。

    用法：
        from app.utils.rag import get_rag

        rag = get_rag()
        rag.add_document("profile", "张三……", source="resume_001")
        answer = rag.ask("profile", "张三擅长什么技术？")
    """

    def __init__(self) -> None:
        self.llm = get_llm()
        self.vec = get_vector_store()

    def add_document(self, collection: str, text: str, *, source: str = "", chunk_size: int = 500) -> int:
        """切块、向量化并写入向量库，返回写入块数。"""
        if not self.vec.has_collection(collection):
            self.vec.create_collection(collection, dim=len(self.llm.embed("test")))
        chunks = _split_text(text, chunk_size=chunk_size)
        texts = [f"【来源:{source}】{c}" if source else c for c in chunks]
        vectors = [self.llm.embed(c) for c in chunks]
        self.vec.insert(collection, vectors, texts)
        return len(chunks)

    def retrieve(self, collection: str, query: str, top_k: int = 5) -> list[dict]:
        """召回与查询最相似的文本块。"""
        vector = self.llm.embed(query)
        return self.vec.search(collection, vector, top_k=top_k)

    def ask(self, collection: str, query: str, *, system: str | None = None, top_k: int = 5) -> str:
        """基于召回结果生成问答。"""
        hits = self.retrieve(collection, query, top_k=top_k)
        context = "\n".join(h["text"] for h in hits) if hits else "（无相关文档）"
        prompt = f"参考以下信息回答用户问题，若信息不足则如实说明。\n\n资料：\n{context}\n\n问题：{query}"
        return self.llm.chat(prompt, system=system or "你是一个严谨的领域助手。")


_rag: RAGTool | None = None


def get_rag() -> RAGTool:
    """获取全局单例的 RAG 工具（懒初始化）。"""
    global _rag
    if _rag is None:
        _rag = RAGTool()
    return _rag
