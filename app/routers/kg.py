"""知识图谱路由（M1：人才画像关系网 / 子图相似 / 全量同步）。

- GET  /kg/talent/{tid}/graph   —— 单人才画像关系网（ECharts graph 直接消费）
- POST /kg/talent/{tid}/similar —— 子图相似人才（共享技能/标签/项目加权计分）
- POST /kg/sync-all            —— 全量重建图谱（验收/运维/答辩用）

图谱服务不可用时所有接口安全降级（空图/空列表/同步失败统计），不抛 500。
读操作沿用 talent:query，写操作沿用 talent:manage。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.db.session import get_db
from app.utils.neo4j_client import get_neo4j_service
from app.utils.response import ok

router = APIRouter()

# ECharts graph 节点类型（前端据此分色）
_NODE_LABELS = {
    "Talent": "人才",
    "Skill": "技能",
    "Tag": "画像标签",
    "Project": "项目",
    "Certificate": "证书",
}

# 类型 → 节点 key 前缀（同名字段跨类型区分，如 Skill 与 Project 可能同名）
_TYPE_PREFIX = {
    "Talent": "t",
    "Skill": "s",
    "Tag": "g",
    "Project": "p",
    "Certificate": "c",
}


def _readable_type(label: str) -> str:
    return _NODE_LABELS.get(label, label)


def _query_graph(tid: int) -> dict:
    """取单人才 1 跳子图并转 ECharts graph 结构（{nodes, edges}）。"""
    svc = get_neo4j_service()
    raw_nodes = svc.execute_query(
        """
        MATCH (t:Talent {tid: $tid})
        OPTIONAL MATCH (t)-[r]->(n)
        RETURN t AS talent, n AS neighbor,
               type(r) AS rel_type,
               labels(n)[0] AS n_label,
               properties(n) AS n_props
        """,
        {"tid": tid},
    )
    nodes: list[dict] = []
    edges: list[dict] = []
    seen_nodes: set[str] = set()
    # 中心人才节点
    center_id = f"{_TYPE_PREFIX['Talent']}-{tid}"
    nodes.append({"id": center_id, "name": f"人才 #{tid}", "nodeType": "Talent",
                  "category": _readable_type("Talent"), "symbolSize": 46})
    seen_nodes.add(center_id)

    for row in raw_nodes:
        rel_type = row.get("rel_type")
        if rel_type is None or not row.get("neighbor"):
            continue
        n_label = row.get("n_label") or "Tag"
        prefix = _TYPE_PREFIX.get(n_label, "n")
        props = row.get("n_props") or {}
        # 属性取数：直接字典 / Node 对象兼容
        name = props.get("name") if isinstance(props, dict) else getattr(props, "name", None)
        nid = f"{prefix}-{name}"
        if nid not in seen_nodes:
            seen_nodes.add(nid)
            nodes.append({"id": nid, "name": str(name), "nodeType": n_label,
                          "category": _readable_type(n_label), "symbolSize": 22})
        edges.append({"source": center_id, "target": nid, "relType": rel_type})
    return {"nodes": nodes, "edges": edges}


def _query_similar(tid: int, limit: int) -> list[dict]:
    """共享邻居加权计分：HAS_SKILL×3 / HAS_PROJECT×2 / 其它×1。"""
    svc = get_neo4j_service()
    raw = svc.execute_query(
        """
        MATCH (t:Talent {tid: $tid})-[r]->(n)
        WITH t, n, type(r) AS rt,
             CASE type(r) WHEN 'HAS_SKILL' THEN 3 WHEN 'HAS_PROJECT' THEN 2 ELSE 1 END AS w
        MATCH (o:Talent)-[r2]->(n)
        WHERE o.tid <> t.tid
        RETURN o.tid AS tid, o.name AS name, o.title AS title,
               count(DISTINCT n) AS shared, sum(w) AS score
        ORDER BY score DESC, shared DESC
        LIMIT $limit
        """,
        {"tid": tid, "limit": limit},
    )
    return [
        {
            "tid": row.get("tid"),
            "name": row.get("name"),
            "title": row.get("title"),
            "shared": row.get("shared"),
            "score": row.get("score"),
        }
        for row in raw
    ]


@router.get("/talent/{tid}/graph", dependencies=[Depends(require_permission("talent:query"))],
            summary="人才画像关系网（1 跳子图）")
def talent_graph(tid: int, db: Session = Depends(get_db)):
    """返回 ECharts graph 可直接消费的 {nodes, edges, meta}。"""
    data = _query_graph(tid)
    meta = {"synced": bool(data["nodes"]), "neighbor_count": len(data["edges"])}
    return ok({**data, "meta": meta})


@router.post("/talent/{tid}/similar", dependencies=[Depends(require_permission("talent:query"))],
             summary="子图相似人才（共享技能/标签/项目加权）")
def talent_similar(tid: int, limit: int = Query(5, ge=1, le=20),
                   db: Session = Depends(get_db)):
    hits = _query_similar(tid, limit)
    return ok({"talent_id": tid, "hits": hits})


@router.post("/sync-all", dependencies=[Depends(require_permission("talent:manage"))],
             summary="全量重建图谱（存量人才一键图谱化）")
def sync_all(db: Session = Depends(get_db)):
    from app.services.kg_sync import sync_all_talent_to_kg  # 惰性导入

    from app.utils.neo4j_client import get_neo4j_service as _svc

    kg = _svc()
    if not kg.ping():
        return ok({"status": "error", "message": "Neo4j 不可用，请先 docker start neo4j", "detail": {}})
    detail = sync_all_talent_to_kg(db)
    return ok({"status": "done", "detail": detail})
