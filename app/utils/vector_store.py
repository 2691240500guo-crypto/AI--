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
        host = settings.MILVUS_HOST
        # 兼容：MILVUS_HOST 未带协议前缀时自动补 http://（pymilvus>=3 要求合法 uri）
        if not host.startswith(("http://", "https://", "tcp://", "unix://")):
            host = f"http://{host}"
        self._client = MilvusClient(
            uri=f"{host}:{settings.MILVUS_PORT}",
            db_name=settings.MILVUS_DB_NAME,
        )
        self.prefix = settings.MILVUS_COLLECTION_PREFIX

    def _name(self, collection: str) -> str:
        return f"{self.prefix}{collection}"

    def create_collection(self, collection: str, dim: int, *, metric: str = "IP") -> None:
        """按集合名创建，维度取决于所选 embedding 模型。

        兼容 pymilvus 2.x/3.x：显式定义 schema（id 自增主键 + text + vector），
        并创建默认向量索引（3.x 下无索引无法 load/search）。
        """
        from pymilvus import CollectionSchema, DataType, FieldSchema

        name = self._name(collection)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields=fields, enable_dynamic_field=True)
        self._client.create_collection(collection_name=name, schema=schema, metric_type=metric)
        # 创建默认向量索引（AUTOINDEX，Milvus 自动选合适索引类型），否则无法 load/search
        try:
            from pymilvus.milvus_client import IndexParams

            index_params = IndexParams()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type=metric)
            self._client.create_index(collection_name=name, index_params=index_params)
        except Exception:
            pass

    def has_collection(self, collection: str) -> bool:
        return self._client.has_collection(self._name(collection))

    def insert(self, collection: str, vectors: list[list[float]], texts: list[str]) -> list[int]:
        """写入向量与对应原文，返回生成的 id 列表。"""
        data = [{"vector": v, "text": t} for v, t in zip(vectors, texts)]
        ids = self._client.insert(collection_name=self._name(collection), data=data)
        return ids.get("ids", list(ids))

    def search(self, collection: str, query_vector: list[float], top_k: int = 5) -> list[dict]:
        """按向量相似度检索，返回含 text 与 score 的结果列表。

        修 2026-09-04：脚本批量向量化（scripts/vectorize_talents.py）写完后再 search，
        pymilvus 2.6 默认 Session 一致性下，新写入的向量偶尔不被已加载的集合视图看到。
        这里在 load 之前先 release，强制刷新已加载段，使新写入的向量立刻可被搜到。
        """
        name = self._name(collection)
        try:
            self._client.release_collection(name)
        except Exception:
            pass
        try:
            self._client.load_collection(name)
        except Exception:
            pass
        res = self._client.search(
            collection_name=name,
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
