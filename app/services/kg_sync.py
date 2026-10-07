"""知识图谱同步（M1：人才/技能/标签/项目/证书 → Neo4j）。

数据源：MySQL 主库（tal_talent + tal_talent_tag/tal_tag + tal_project + tal_certificate）。
设计：
- ``sync_talent_to_kg`` 增量同步单个人才：先 DETACH 该人才旧子图再重建（幂等，重跑/重解析结果一致）；
- ``sync_all_talent_to_kg`` 全量重建（供 /kg/sync-all 与运维脚本，分批防大事务）；
- Neo4j 不可用/异常一律降级：返回 False + logger.warning，绝不阻塞 MySQL 主流程
  （与 resume_upload_service 的向量化/自动匹配钩子同一容错风格）。

图谱节点建模（v1）：
- (:Talent {tid, name, title, company})              人才
- (:Skill  {name})                                   专业技能（tal_tag category='skill'）
- (:Tag    {name, category})                         其余画像维度（level/exp/quality/potential/specialty/industry/custom）
- (:Project {name})                                  项目经历（tal_project）
- (:Certificate {name})                              证书（tal_certificate）

关系：HAS_SKILL(score)/HAS_TAG(score,category)/HAS_PROJECT(role)/HAS_CERTIFICATE(level)
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.talent import Talent, TalentTalentTag

logger = logging.getLogger(__name__)

# 作为独立 Skill 节点提升的标签维度；其余维度落 Tag 节点（保留 category 属性）
_SKILL_CATEGORIES = ("skill",)

# 每次全量同步的批量大小（防止单个事务过大拖慢 Neo4j）
_SYNC_BATCH = 50


def _load_talent(db: Session, talent_id: int) -> Talent | None:
    """带标签/项目/证书关联读人才；不存在或已失效返回 None。"""
    return (
        db.query(Talent)
        .options(
            joinedload(Talent.tag_rels).joinedload(TalentTalentTag.tag),
            joinedload(Talent.projects),
            joinedload(Talent.certificates),
        )
        .filter(Talent.id == talent_id, Talent.status == 1)
        .first()
    )


def _build_payload(talent: Talent) -> dict[str, Any]:
    """把 ORM 人才组织成图谱写入载荷。"""
    skills: list[dict[str, Any]] = []
    tags: list[dict[str, Any]] = []
    for rel in talent.tag_rels:
        tag = rel.tag
        if tag is None or not tag.name:
            continue
        item = {"name": tag.name, "score": rel.score}
        if tag.category in _SKILL_CATEGORIES:
            skills.append(item)
        else:
            item["category"] = tag.category or "custom"
            tags.append(item)
    projects = [
        {"name": p.name, "role": p.role}
        for p in talent.projects
        if p.name
    ]
    certificates = [
        {"name": c.name, "level": c.level}
        for c in talent.certificates
        if c.name
    ]
    return {
        "tid": talent.id,
        "name": talent.name,
        "title": talent.current_title,
        "company": talent.current_company,
        "skills": skills,
        "tags": tags,
        "projects": projects,
        "certificates": certificates,
    }


def _write_to_neo4j(payload: dict[str, Any]) -> bool:
    """单人才写图（幂等重建），返回是否成功。Neo4j 服务不可用由调用方感知。"""
    from app.utils.neo4j_client import get_neo4j_service  # 惰性导入，避免服务启动即依赖 Neo4j

    service = get_neo4j_service()
    if not service.ping():
        return False

    def _tx(tx) -> None:
        # 1) 清旧子图（只删该人才与自身关系，共享 Skill/Tag/Project/Certificate 节点保留）
        tx.run("MATCH (t:Talent {tid: $tid}) DETACH DELETE t", tid=payload["tid"])
        # 2) 重建人才节点
        tx.run(
            """
            CREATE (t:Talent {tid: $tid, name: $name})
            SET t.title = $title, t.company = $company
            """,
            tid=payload["tid"], name=payload["name"],
            title=payload.get("title"), company=payload.get("company"),
        )
        # 3) 技能 / 标签 / 项目 / 证书
        # 注意：Neo4j MERGE 关系不能携带 null 属性值（会抛 SemanticError），
        # 故先 MERGE 空关系再 SET 属性（SET 允许 null，如 score/role 缺省场景）。
        for s in payload["skills"]:
            tx.run(
                "MATCH (t:Talent {tid: $tid}) "
                "MERGE (n:Skill {name: $name}) "
                "MERGE (t)-[r:HAS_SKILL]->(n) "
                "SET r.score = $score",
                tid=payload["tid"], name=s["name"], score=s.get("score"),
            )
        for g in payload["tags"]:
            tx.run(
                "MATCH (t:Talent {tid: $tid}) "
                "MERGE (n:Tag {name: $name}) "
                "SET n.category = $category "
                "MERGE (t)-[r:HAS_TAG]->(n) "
                "SET r.score = $score",
                tid=payload["tid"], name=g["name"],
                category=g.get("category", "custom"), score=g.get("score"),
            )
        for p in payload["projects"]:
            tx.run(
                "MATCH (t:Talent {tid: $tid}) "
                "MERGE (n:Project {name: $name}) "
                "MERGE (t)-[r:HAS_PROJECT]->(n) "
                "SET r.role = $role",
                tid=payload["tid"], name=p["name"], role=p.get("role"),
            )
        for c in payload["certificates"]:
            tx.run(
                "MATCH (t:Talent {tid: $tid}) "
                "MERGE (n:Certificate {name: $name}) "
                "MERGE (t)-[r:HAS_CERTIFICATE]->(n) "
                "SET r.level = $level",
                tid=payload["tid"], name=c["name"], level=c.get("level"),
            )
        return True

    return bool(service.execute_transaction(_tx, default=False))


def sync_talent_to_kg(db: Session, talent_id: int) -> bool:
    """同步单个人才到图谱（幂等）。

    - 调用方（简历上传/手动建档/重跑解析）失败不阻塞主流程：函数本身只记日志返回 False。
    - 返回 True 表示已写图；False 表示人才无效或 Neo4j 不可用/写入失败。
    """
    talent = _load_talent(db, talent_id)
    if talent is None:
        logger.info("[kg] 跳过图谱同步：人才 #%s 不存在或已失效", talent_id)
        return False
    payload = _build_payload(talent)
    if not (payload["skills"] or payload["tags"] or payload["projects"] or payload["certificates"]):
        logger.info("[kg] 人才 #%s 无画像数据（技能/标签/项目/证书为空），跳过", talent_id)
        return False
    return _write_to_neo4j(payload)


def safe_sync_talent(db: Session, talent_id: int, *, source: str = "") -> bool:
    """业务链路上的安全钩子：内部吞掉一切异常，绝不阻塞 MySQL 主流程。

    供简历上传 / 手动建档 / 重跑解析等调用方统一使用；返回 True=已同步。
    """
    try:
        return sync_talent_to_kg(db, talent_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[kg] %s后图谱同步异常（降级，不影响主流程）：%s",
                       source or "人才变更", exc)
        return False


def sync_all_talent_to_kg(db: Session, *, batch: int = _SYNC_BATCH) -> dict[str, Any]:
    """全量重建图谱：遍历所有在档人才并逐个同步（失败不中断）。

    :return: {"total": 总数, "ok": 成功数, "failed": 失败数, "failed_ids": [...]}
    """
    ids = [
        row[0]
        for row in db.query(Talent.id).filter(Talent.status == 1).order_by(Talent.id).all()
    ]
    total, ok, failed, failed_ids = len(ids), 0, 0, []
    for i in range(0, total, batch):
        chunk = ids[i:i + batch]
        for tid in chunk:
            try:
                if sync_talent_to_kg(db, tid):
                    ok += 1
                else:
                    failed += 1
                    failed_ids.append(tid)
            except Exception as exc:  # noqa: BLE001 单条异常不中断整批
                logger.warning("[kg] 全量同步人才 #%s 异常：%s", tid, exc)
                failed += 1
                failed_ids.append(tid)
    logger.info("[kg] 全量同步完成 total=%s ok=%s failed=%s", total, ok, failed)
    return {"total": total, "ok": ok, "failed": failed, "failed_ids": failed_ids}
