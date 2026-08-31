"""向量数据库客户端（Milvus）。

统一封装 Milvus 的建集合、插入、检索等常用能力。
团队成员需要向量检索功能时直接调用本类，无需关心 Collection/Search 细节。
依赖惰性导入，pymilvus 未安装时不影响其它模块。
"""
from __future__ import annotations

from app.core.config import get_settings


class VectorStore:
    """Milvus 向量库客户端。

    用法：
        from app.utils.vector_store import get_vector_store

        v = get_vector_store()
        v.create_collection("profile", dim=768)
        v.insert("profile", vectors, texts)
        hits = v.search("profile", query_vector, top_k=5)
    """

    def __init__(self) -> None:
        from pymilvus import MilvusClient  # 惰性导入

        settings = get_settings()
        self._client = MilvusClient(
            uri=f"{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
            db_name=settings.MILVUS_DB_NAME,
        )
        self.prefix = settings.MILVUS_COLLECTION_PREFIX

    def _name(self, collection: str) -> str:
        return f"{self.prefix}{collection}"

    def create_collection(self, collection: str, dim: int, *, metric: str = "IP") -> None:
        """按集合名创建，维度取决于所选 embedding 模型。"""
        self._client.create_collection(
            collection_name=self._name(collection), dimension=dim, metric_type=metric,
        )

    def has_collection(self, collection: str) -> bool:
        return self._client.has_collection(self._name(collection))

    def insert(self, collection: str, vectors: list[list[float]], texts: list[str]) -> list[int]:
        """写入向量与对应原文，返回生成的 id 列表。"""
        data = [{"vector": v, "text": t} for v, t in zip(vectors, texts)]
        ids = self._client.insert(collection_name=self._name(collection), data=data)
        return ids.get("ids", list(ids))

    def search(self, collection: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """按向量相似度检索，返回含 text 与 score 的结果列表。"""
        res = self._client.search(
            collection_name=self._name(collection),
            data=[query_vector],
            limit=top_k,
            output_fields=["text"],
        )
        hits = res[0] if res else []
        return [
            {"id": h["id"], "text": h["entity"].get("text", ""), "score": h["distance"]}
            for h in hits
        ]

    def delete_collection(self, collection: str) -> None:
        self._client.drop_collection(self._name(collection))


_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """获取全局单例的向量库客户端（懒初始化）。"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
