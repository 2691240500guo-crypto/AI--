"""岗位匹配路由（M 域）。

接口：
- GET/POST/PUT/DELETE /matching/positions          岗位 CRUD（M-1）
- POST /matching/positions/{id}/vector             岗位画像向量化（M-2）
- POST /matching/match                             双向匹配（M-3）
- GET  /matching/results                           匹配结果列表（M-3/M-4）
- GET  /matching/result/{id}/explain               匹配解释依据（M-4）
- GET  /matching/alerts                            储备/空缺预警（M-5）
- GET/POST/PUT/DELETE /matching/rules              匹配规则 CRUD（支撑 M-3）
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.dao.matching import MatchPushLogDAO, MatchResultDAO, MatchRuleDAO, PosPositionDAO
from app.db.session import get_db
from app.models.matching import MatchResult, PosPosition, MatchRule, MatchPushLog
from app.schemas.matching import (
    AgentChatRequest,
    AgentParseRequest,
    AgentReverseRequest,
    AgentRunRequest,
    MatchRequest,
    MatchResultOut,
    MatchRuleCreate,
    MatchRuleOut,
    MatchTaskOut,
    PositionCreate,
    PositionOut,
    PositionUpdate,
    VectorOut,
)
from app.services.matching import MatchingService
from app.ai.agents.match_agent import MatchAgent
from app.utils.pagination import PageParams, count_rows, paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("matching:*"))])


# ==================== 岗位 CRUD（M-1） ====================

@router.get("/positions")
def list_positions(
    keyword: str | None = Query(None, description="按名称/编码模糊搜索"),
    dept_id: int | None = None,
    status: int | None = None,
    page: PageParams = Depends(PageParams),
    db: Session = Depends(get_db),
):
    where = []
    if keyword:
        like = f"%{keyword}%"
        where.append(PosPosition.name.like(like) | PosPosition.code.like(like))
    if dept_id is not None:
        where.append(PosPosition.dept_id == dept_id)
    if status is not None:
        where.append(PosPosition.status == status)
    total = count_rows(db, PosPosition, *where)
    rows = PosPositionDAO.list(db, *where, offset=(page.page - 1) * page.page_size,
                               limit=page.page_size, order_by=PosPosition.id.desc())
    return ok(paged_result([PositionOut.model_validate(r) for r in rows], page.page, page.page_size, total))


@router.post("/positions")
def create_position(body: PositionCreate, db: Session = Depends(get_db)):
    if PosPositionDAO.get_by_code(db, body.code):
        raise HTTPException(400, f"岗位编码 {body.code} 已存在")
    obj = PosPositionDAO.create(db, **body.model_dump())
    db.commit()
    return ok(PositionOut.model_validate(obj))


@router.get("/positions/{pid}")
def get_position(pid: int, db: Session = Depends(get_db)):
    p = PosPositionDAO.get(db, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    return ok(PositionOut.model_validate(p))


@router.put("/positions/{pid}")
def update_position(pid: int, body: PositionUpdate, db: Session = Depends(get_db)):
    p = PosPositionDAO.get(db, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    if body.code and body.code != p.code and PosPositionDAO.get_by_code(db, body.code):
        raise HTTPException(400, f"岗位编码 {body.code} 已存在")
    fields = body.model_dump(exclude_unset=True)
    PosPositionDAO.update(db, p, **fields)
    db.commit()
    return ok(PositionOut.model_validate(p))


@router.delete("/positions/{pid}")
def delete_position(pid: int, db: Session = Depends(get_db)):
    p = PosPositionDAO.get(db, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    # 有关联匹配结果时禁止删除，避免脏数据
    if db.scalar(select(func.count()).select_from(MatchResult).where(MatchResult.position_id == pid)):
        raise HTTPException(400, "该岗位存在匹配结果，不能删除（可改为停用）")
    PosPositionDAO.delete(db, p)
    db.commit()
    return ok()


# ==================== 岗位画像向量化（M-2） ====================

@router.post("/positions/{pid}/vector")
def vectorize_position(pid: int, db: Session = Depends(get_db)):
    data = MatchingService.vectorize_position(db, pid)
    return ok(VectorOut(**data))


# ==================== 匹配规则 CRUD（支撑 M-3） ====================

@router.get("/rules")
def list_rules(db: Session = Depends(get_db)):
    rows = MatchRuleDAO.list(db, limit=100, order_by=MatchRule.id.desc())
    return ok([MatchRuleOut.model_validate(r) for r in rows])


@router.post("/rules")
def create_rule(body: MatchRuleCreate, db: Session = Depends(get_db)):
    rule_json = json.dumps(body.rule_json, ensure_ascii=False) if body.rule_json else None
    obj = MatchRuleDAO.create(db, name=body.name, rule_json=rule_json, status=body.status)
    db.commit()
    return ok(MatchRuleOut.model_validate(obj))


# ==================== 双向匹配（M-3） ====================

@router.post("/match")
def run_match(body: MatchRequest, db: Session = Depends(get_db)):
    saved = MatchingService.run_match(
        db, talent_ids=body.talent_ids, position_ids=body.position_ids,
        rule_id=body.rule_id, top_k=body.top_k,
    )
    return ok(MatchTaskOut(total=len(saved), results=saved))


@router.get("/results")
def list_results(
    talent_id: int | None = None,
    position_id: int | None = None,
    min_score: float | None = None,
    page: PageParams = Depends(PageParams),
    db: Session = Depends(get_db),
):
    where = []
    if talent_id is not None:
        where.append(MatchResult.talent_id == talent_id)
    if position_id is not None:
        where.append(MatchResult.position_id == position_id)
    if min_score is not None:
        where.append(MatchResult.score >= min_score)
    total = count_rows(db, MatchResult, *where)
    rows = MatchResultDAO.list(db, *where, offset=(page.page - 1) * page.page_size,
                               limit=page.page_size, order_by=MatchResult.score.desc())
    return ok(paged_result([MatchResultOut.model_validate(r) for r in rows], page.page, page.page_size, total))


@router.get("/result/{mid}/explain")
def get_explain(mid: int, db: Session = Depends(get_db)):
    explanation = MatchingService.explain(db, mid)
    return ok({"match_id": mid, "explain": explanation})


# ==================== 储备/空缺预警（M-5） ====================

@router.get("/alerts")
def list_alerts(position_id: int | None = None, db: Session = Depends(get_db)):
    where = []
    if position_id is not None:
        where.append(MatchPushLog.match_id.in_(
            select(MatchResult.id).where(MatchResult.position_id == position_id)
        ))
    rows = MatchPushLogDAO.list(db, *where, limit=200, order_by=MatchPushLog.id.desc())
    return ok([{"id": r.id, "match_id": r.match_id, "type": r.type,
                "target_user": r.target_user, "message_id": r.message_id,
                "created_at": r.created_at} for r in rows])


@router.post("/alerts/generate")
def generate_alerts(position_id: int | None = None, db: Session = Depends(get_db)):
    alerts = MatchingService.generate_alerts(db, position_id=position_id)
    return ok({"total": len(alerts), "alerts": alerts})


# ==================== 岗位人才匹配 Agent（AI） ====================

@router.post("/agent/parse")
def agent_parse_requirement(body: AgentParseRequest, db: Session = Depends(get_db)):
    """岗位智能解析：AI 拆解任职要求/技能标准/经验门槛/学历/综合素质 → 标签体系。"""
    result = MatchAgent.parse_requirement(db, body.position_id)
    return ok(result)


@router.post("/agent/run")
def agent_run_match(body: AgentRunRequest, db: Session = Depends(get_db)):
    """岗位→人才匹配：向量检索 + 硬过滤 + 软加权 + 排序 + 落库 + 解释。"""
    filters = {
        "degree_required": body.degree_required,
        "years_required": body.years_required,
        "mandatory_skills": body.mandatory_skills,
    }
    results = MatchAgent.run_match(
        db, body.position_id, top_k=body.top_k,
        min_score=body.min_score, gen_explain=body.gen_explain,
        filters=filters,
    )
    return ok({"total": len(results), "results": results})


@router.post("/agent/reverse")
def agent_reverse_match(body: AgentReverseRequest, db: Session = Depends(get_db)):
    """人才→岗位反向匹配：人才画像 → 检索岗位 → 打分排序。"""
    results = MatchAgent.reverse_match(db, body.talent_id, top_k=body.top_k,
                                       min_score=body.min_score)
    return ok({"total": len(results), "results": results})


@router.post("/agent/chat")
def agent_chat(body: AgentChatRequest, db: Session = Depends(get_db)):
    """自然语言操作：意图识别 → 参数抽取 → 执行 → 自然语言回复。"""
    return ok(MatchAgent.chat(db, body.message))
