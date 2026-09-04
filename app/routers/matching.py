"""岗位匹配路由（M 域）。

接口：
- GET/POST/PUT/DELETE /matching/positions          岗位 CRUD（M-1）
- POST /matching/positions/{id}/vector             岗位画像向量化（M-2）
- POST /matching/match                             双向匹配（M-3）
- GET  /matching/results                           匹配结果列表（M-3/M-4，支持保温/待跟进筛选）
- GET  /matching/result/{id}/explain               匹配解释依据（M-4）
- PUT  /matching/result/{id}/warm ｜ POST /warm/batch  储备人才保温（需求4，单条/批量）
- GET  /matching/alerts ｜ POST /alerts/generate   储备/空缺预警（M-5，读侧富化/24h 去重）
- GET/POST/PUT/DELETE /matching/rules              匹配规则 CRUD（支撑 M-3）
"""
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import require_any_perm
from app.core.config import get_settings
from app.core.redis_client import get_redis_service
from app.dao.matching import MatchPushLogDAO, MatchResultDAO, MatchRuleDAO, PosPositionDAO
from app.db.session import get_db
from app.models.matching import MatchResult, PosPosition, MatchRule, MatchPushLog
from app.schemas.matching import (
    AgentChatRequest,
    AgentMatchRequest,
    AgentParseRequest,
    AgentReverseRequest,
    AgentRunRequest,
    EvalRequest,
    MatchRequest,
    MatchResultOut,
    MatchRuleCreate,
    MatchRuleOut,
    MatchTaskOut,
    PositionCreate,
    PositionOut,
    PositionUpdate,
    ResultStatusRequest,
    VectorOut,
    WarmBatchRequest,
    WarmRequest,
)
from app.services.matching import MatchingService
from app.ai.agents.match_agent import MatchAgent
from app.utils.pagination import PageParams, count_rows, paged_result
from app.utils.response import ok

# 岗位匹配模块入口：持有任一岗位匹配子权限即放行（菜单授权的是叶子 perm：position/result/agent/alert；
# 兼容历史目录授权 matching:*），避免"菜单授权了但路由要求别的码"导致 403。
router = APIRouter(dependencies=[Depends(require_any_perm(
    "matching:*", "matching:position", "matching:result", "matching:agent", "matching:alert",
))])

logger = logging.getLogger("matching")


# ==================== 岗位 CRUD（M-1） ====================

@router.get("/positions")
def list_positions(
    keyword: str | None = Query(None, description="按名称/编码模糊搜索"),
    dept_id: int | None = None,
    status: int | None = None,
    page: PageParams = Depends(PageParams),
    db: Session = Depends(get_db),
):
    def load_position_page() -> dict:
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
        items = [PositionOut.model_validate(row).model_dump(mode="json") for row in rows]
        return paged_result(items, page.page, page.page_size, total)

    cache_name = f"positions:{keyword or ''}:{dept_id}:{status}:{page.page}:{page.page_size}"
    return ok(get_redis_service().cached_json(
        "analytics", cache_name, get_settings().REDIS_HOME_TTL, load_position_page
    ))


@router.post("/positions")
def create_position(body: PositionCreate, db: Session = Depends(get_db)):
    if PosPositionDAO.get_by_code(db, body.code):
        raise HTTPException(400, f"岗位编码 {body.code} 已存在")
    # hq+ 2026-09-04：防御性校验部门 ID（前端未选时可空，但选了则必须存在）
    if body.dept_id is not None:
        from sqlalchemy import text as sa_text_dept
        exists = db.scalar(sa_text_dept("SELECT 1 FROM sys_dept WHERE id=:i"), {"i": body.dept_id})
        if not exists:
            raise HTTPException(400, f"部门 ID {body.dept_id} 不存在，请先在系统管理→部门管理创建")
    obj = PosPositionDAO.create(db, **body.model_dump())
    db.commit()
    # hq+ 2026-09-04：新增启用岗位 → 自动解析说明书 + 写向量（无需手动点向量化）
    _auto_parse_and_vectorize(db, obj)
    return ok(PositionOut.model_validate(obj))


@router.get("/positions/vacancy-count", summary="招聘中岗位数（filled<headcount）")
def get_vacancy_position_count(db: Session = Depends(get_db)):
    """首页"在招岗位"卡片数据源。"""
    from app.services.matching import MatchingService
    return ok({"vacancy": MatchingService.vacancy_count(db)})


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
    # hq+ 2026-09-04：编辑时若改了部门 ID，校验存在
    if "dept_id" in fields and fields["dept_id"] is not None:
        from sqlalchemy import text as sa_text_dept2
        exists = db.scalar(sa_text_dept2("SELECT 1 FROM sys_dept WHERE id=:i"), {"i": fields["dept_id"]})
        if not exists:
            raise HTTPException(400, f"部门 ID {fields['dept_id']} 不存在，请先在系统管理→部门管理创建")
    PosPositionDAO.update(db, p, **fields)
    db.commit()
    # 岗位编制/到岗变更后自动触发空缺预警（需求4「实时监控」最后一块）：
    # 仅当变更涉及 headcount/filled 才触发；24h 去重由 auto_push_vacancy 内部保证，
    # 失败仅告警、不影响岗位保存返回。
    if "headcount" in fields or "filled" in fields:
        try:
            auto = MatchingService.auto_push_vacancy(db, [pid])
            if auto:
                logger.info("[alerts] 岗位 %s 编制/到岗变更后自动推送空缺预警 %d 条", pid, len(auto))
        except Exception as e:  # noqa: BLE001
            logger.warning("[alerts] 岗位变更后自动预警失败（忽略）: %s", e)
    # hq+ 2026-09-04：编辑时若启用 + 说明书非空，自动重跑解析 + 向量化
    _auto_parse_and_vectorize(db, p)
    return ok(PositionOut.model_validate(p))


@router.delete("/positions/{pid}")
def delete_position(pid: int, db: Session = Depends(get_db)):
    """删除岗位：级联清理关联数据再删岗位行
    （FK 链：match_push_log.match_id → match_result.id → pos_position.id，
     必须按 match_push_log → match_result → pos_position 顺序删，否则外键报错 1451）
    """
    from sqlalchemy import text as sa_text
    p = PosPositionDAO.get(db, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    deleted_mr = 0
    deleted_mpl = 0
    try:
        # 1. 先删 match_push_log（依赖 match_result）
        deleted_mpl = db.execute(
            sa_text("DELETE FROM match_push_log WHERE match_id IN "
                    "(SELECT id FROM match_result WHERE position_id = :pid)"),
            {"pid": pid},
        ).rowcount
        # 2. 再删 match_result（依赖 pos_position）
        deleted_mr = db.execute(
            sa_text("DELETE FROM match_result WHERE position_id = :pid"),
            {"pid": pid},
        ).rowcount
        # 3. 清掉 Milvus 里该岗位的向量（用画像文本的【岗位id:N|】前缀过滤）
        try:
            from app.utils.vector_store import get_vector_store
            get_vector_store()._client.delete(
                collection_name="talent_position_vec",
                filter=f'text like "%【岗位id:{pid}|%"',
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("[position] 清理 Milvus 向量失败 id=%s: %s", pid, e)
        # 4. 删岗位行
        PosPositionDAO.delete(db, p)
        db.commit()
    except Exception as e:  # noqa: BLE001
        db.rollback()
        raise HTTPException(500, f"删除岗位失败：{e}") from e
    return ok({"position_id": pid,
              "deleted_match_results": deleted_mr,
              "deleted_push_logs": deleted_mpl})


# hq+ 2026-09-04：新增/编辑岗位后，自动跑需求解析 + 画像向量化（替代手动向量化按钮）
def _auto_parse_and_vectorize(db: Session, p: PosPosition) -> None:
    """启用岗位且说明书非空时，自动解析+写入向量；任一步失败仅日志，不影响保存。"""
    if not getattr(p, "status", 0):
        return
    desc = (getattr(p, "description", "") or "").strip()
    if not desc:
        return
    try:
        from app.ai.agents.match_agent import MatchAgent
        try:
            MatchAgent.parse_requirement(db, p.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[position] 自动解析失败 id=%s: %s", p.id, e)
        try:
            MatchingService.vectorize_position(db, p.id)
        except Exception as e:  # noqa: BLE001
            logger.warning("[position] 自动向量化失败 id=%s: %s", p.id, e)
    except Exception as e:  # noqa: BLE001
        logger.warning("[position] 自动向量化整体失败 id=%s: %s", p.id, e)


# ==================== 岗位画像向量化（M-2） ====================

@router.post("/positions/{pid}/vector")
def vectorize_position(pid: int, db: Session = Depends(get_db)):
    data = MatchingService.vectorize_position(db, pid)
    return ok(VectorOut(**data))


@router.post("/positions/{pid}/jd-import", summary="导入岗位说明书文件（PDF/DOCX/TXT/MD/图片），解析文本返回供确认")
@router.post("/positions/jd-preview", summary="预览岗位说明书（不依赖岗位 pid，新增阶段先用）")
async def preview_position_description(
    file: UploadFile = File(..., description="岗位说明书文件 PDF/DOCX/TXT/MD/图片"),
):
    """新增岗位时先用本接口拿到解析文本，填到表单 description 后再保存岗位。"""
    if not file.filename:
        raise HTTPException(400, "请选择文件")
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传的文件为空")
    try:
        from app.utils.file_parser import parse_bytes
        suffix = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
        text = parse_bytes(content, suffix)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        raise HTTPException(400, f"文件解析失败：{e}") from e
    if not text:
        raise HTTPException(400, "未能从文件抽到任何文字，请检查文件内容或格式")
    return ok({"filename": file.filename, "length": len(text), "text": text})


async def import_position_description(
    pid: int,
    file: UploadFile = File(..., description="岗位说明书文件 PDF/DOCX/TXT/MD/图片"),
    db: Session = Depends(get_db),
):
    """上传岗位说明书文件，抽文本（复用 T 域 file_parser），**不直接落库**，仅返回解析文本。

    前端把解析结果填入岗位 description 后在保存时一并提交，避免误覆盖已有说明书。
    """
    p = PosPositionDAO.get(db, pid)
    if not p:
        raise HTTPException(404, "岗位不存在")
    if not file.filename:
        raise HTTPException(400, "请选择文件")
    content = await file.read()
    if not content:
        raise HTTPException(400, "上传的文件为空")
    try:
        from app.utils.file_parser import parse_bytes
        suffix = ("." + file.filename.rsplit(".", 1)[-1].lower()) if "." in file.filename else ""
        text = parse_bytes(content, suffix)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        raise HTTPException(400, f"文件解析失败：{e}") from e
    if not text:
        raise HTTPException(400, "未能从文件抽到任何文字，请检查文件内容或格式")
    return ok({"position_id": p.id, "filename": file.filename, "length": len(text), "text": text})


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
    # ①事件自动触发：本次匹配涉及的空缺岗位有新可补位储备 → 自动推送（失败不影响主流程）
    try:
        pids = sorted({int(s["position_id"]) for s in saved if s.get("position_id")})
        if pids:
            auto = MatchingService.auto_push_vacancy(db, pids)
            if auto:
                logger.info("[alerts] 发起匹配后自动推送空缺补位预警 %d 条: %s", len(auto), [a.get("position_id") for a in auto])
    except Exception as e:  # noqa: BLE001
        logger.warning("[alerts] 发起匹配后自动推送失败（忽略）: %s", e)
    return ok(MatchTaskOut(total=len(saved), results=saved))


@router.get("/results")
def list_results(
    talent_id: int | None = None,
    talent_name: str | None = Query(None, description="人才姓名（模糊匹配，可部分匹配）"),
    position_id: int | None = None,
    min_score: float | None = None,
    status: int | None = Query(None, ge=0, le=2, description="匹配状态 0候选 1推荐 2录用"),
    warm_level: int | None = Query(None, ge=0, le=3, description="保温等级 0无 1低 2中 3高"),
    need_follow_up_days: int | None = Query(None, ge=1, description="保温中且超过 N 天未跟进"),
    sort_by: str | None = Query(None, description="排序：score|rank|level|exp_years|quality_score|skill|degree|years|quality"),
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
    if status is not None:
        where.append(MatchResult.status == status)
    if warm_level is not None:
        where.append(MatchResult.warm_level == warm_level)
    if need_follow_up_days is not None:
        # 保温管理视角：已在保温(>0)但超过 N 天未跟进（含从未跟进）的储备人群
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=need_follow_up_days)
        where.append(MatchResult.warm_level > 0)
        where.append(or_(MatchResult.last_follow_up.is_(None),
                         MatchResult.last_follow_up < cutoff))
    # hq+ 2026-09-04：支持按人才姓名模糊筛选（先反查 tal_talent.name 命中 ID 集合，
    # 再走 MatchResult.talent_id.in_，各排序分支通用，无需 JOIN）
    if talent_name and talent_name.strip():
        from sqlalchemy import select as sa_sel_name
        from app.models.talent import Talent as _TalentForName
        kw = f"%{talent_name.strip()}%"
        tids = db.scalars(
            sa_sel_name(_TalentForName.id).where(_TalentForName.name.like(kw))
        ).all()
        if tids:
            where.append(MatchResult.talent_id.in_(list(tids)))
        else:
            where.append(MatchResult.id < 0)  # 姓名无命中 → 空结果
    total = count_rows(db, MatchResult, *where)

    # 排序在 SQL 层完成（避免"只排当前页"导致跨页序不准）：
    # - score：默认匹配度降序
    # - rank：名次升序，未排名(NULL)放最后
    # - skill/degree/years/quality：读取 dimension_json 内维度分降序
    #   注意：用 func.cast(..., Numeric) 让 MySQL 生成 DECIMAL、SQLite 生成 NUMERIC（MySQL 不接受 AS NUMERIC）
    from sqlalchemy import text as sa_text
    from sqlalchemy import func as sa_func
    from sqlalchemy import Numeric as sa_Numeric

    sort_key = (sort_by or "score").strip()
    # 需 JOIN 档案/研判表的三类排序（DAO.list 不支持 join，这里 inline）：
    #   level=S/A/B/C(字典序=等级序)、exp_years=真实从业年限、quality_score=研判综合分
    if sort_key in ("exp_years", "quality_score"):
        from sqlalchemy import select as sa_select
        from app.models.talent import Talent
        from app.models.talent_report import TalentReport
        # 键名白名单已在上方约束（仅两值），col 为三元常量不注入
        col = ("COALESCE(tal_talent.years_experience,0)" if sort_key == "exp_years"
               else "COALESCE(tal_talent_report.composite_score,0)")
        stmt = (sa_select(MatchResult)
                .outerjoin(Talent, MatchResult.talent_id == Talent.id)
                .outerjoin(TalentReport, TalentReport.talent_id == Talent.id)
                .where(*where)
                .order_by(sa_text(f"{col} DESC, match_result.score DESC, match_result.id DESC"))
                .offset((page.page - 1) * page.page_size)
                .limit(page.page_size))
        row = [MatchResultOut.model_validate(r) for r in db.scalars(stmt).all()]
    # 能力等级排序需要 LEFT JOIN tal_talent.level（DAO.list 不支持 join，这里 inline）
    elif sort_key == "level":
        from sqlalchemy import select as sa_select
        from app.models.talent import Talent
        stmt = (sa_select(MatchResult)
                .join(Talent, MatchResult.talent_id == Talent.id)
                .where(*where)
                .order_by(sa_text(
                    "CASE WHEN tal_talent.level IS NULL OR tal_talent.level = '' "
                    "THEN 1 ELSE 0 END, tal_talent.level DESC, "
                    "match_result.score DESC, match_result.id DESC"
                ))
                .offset((page.page - 1) * page.page_size)
                .limit(page.page_size))
        row = [MatchResultOut.model_validate(r) for r in db.scalars(stmt).all()]
    else:
        if sort_key == "rank":
            order_expr = sa_text("CASE WHEN match_result.rank IS NULL THEN 1 ELSE 0 END, match_result.rank ASC, match_result.id DESC")
            row = [MatchResultOut.model_validate(r) for r in
                   MatchResultDAO.list(db, *where, offset=(page.page - 1) * page.page_size,
                                       limit=page.page_size, order_by=order_expr)]
        elif sort_key in ("skill", "degree", "years", "quality"):
            # 维度排序需要 CAST json_extract → Numeric（多列 order_by；DAO.list 只支持单表达式，这里 inline）
            from sqlalchemy import select as sa_select
            order_keys = sa_func.cast(
                sa_func.json_extract(MatchResult.dimension_json, f"$.{sort_key}"),
                sa_Numeric,
            ).desc()
            stmt = (sa_select(MatchResult).where(*where)
                    .order_by(order_keys, MatchResult.score.desc(), MatchResult.id.desc())
                    .offset((page.page - 1) * page.page_size)
                    .limit(page.page_size))
            row = [MatchResultOut.model_validate(r) for r in db.scalars(stmt).all()]
        else:
            row = [MatchResultOut.model_validate(r) for r in
                   MatchResultDAO.list(db, *where, offset=(page.page - 1) * page.page_size,
                                       limit=page.page_size, order_by=MatchResult.score.desc())]

    # hq+ 2026-09-04：响应统一补人才姓名/现职（读侧只读复用 T 域 tal_talent）
    items: list[dict] = []
    if row:
        from sqlalchemy import select as sa_select_enrich
        from app.models.talent import Talent as _TalentEnrich
        tids = list({getattr(r, "talent_id", None) for r in row if getattr(r, "talent_id", None)})
        tmap: dict[int, _TalentEnrich] = {}
        if tids:
            tmap = {t.id: t for t in db.scalars(
                sa_select_enrich(_TalentEnrich).where(_TalentEnrich.id.in_(tids))).all()}
        for r in row:
            payload = r.model_dump() if isinstance(r, MatchResultOut) else MatchResultOut.model_validate(r).model_dump()
            t = tmap.get(getattr(r, "talent_id", None))
            payload["talent_name"] = t.name if t else None
            payload["talent_title"] = t.current_title if t else None
            items.append(payload)
    return ok(paged_result(items, page.page, page.page_size, total))


@router.get("/result/{mid}/explain")
def get_explain(mid: int, force: bool = Query(False, description="force=1 时强制重新生成解释"), db: Session = Depends(get_db)):
    explanation = MatchingService.explain(db, mid, force=force)
    return ok({"match_id": mid, "explain": explanation})


@router.put("/result/{mid}/status")
def update_result_status(mid: int, body: ResultStatusRequest, db: Session = Depends(get_db)):
    """更新匹配结果状态：0候选 / 1推荐 / 2录用（操作闭环，录用后下次 run_match 不覆盖）。"""
    from app.services.matching import MatchingService
    return ok(MatchingService.update_status(db, match_id=mid, status=body.status, note=body.note))


@router.put("/result/{mid}/warm")
def update_warm(mid: int, body: WarmRequest, db: Session = Depends(get_db)):
    """储备人才保温更新（需求4）：设置保温等级并刷新跟进时间。"""
    from datetime import datetime
    rec = MatchResultDAO.get(db, mid)
    if not rec:
        raise HTTPException(404, "匹配结果不存在")
    rec.warm_level = body.warm_level
    if body.warm_level > 0:
        rec.last_follow_up = datetime.now()
    else:
        rec.last_follow_up = None
    db.commit()
    return ok({"match_id": rec.id, "warm_level": rec.warm_level, "last_follow_up": rec.last_follow_up})


@router.post("/warm/batch", summary="批量设置保温等级（需求4）")
def batch_warm(body: WarmBatchRequest, db: Session = Depends(get_db)):
    """批量保温：对一批匹配结果统一设置保温等级（0无 1低 2中 3高），并刷新/清空跟进时间。"""
    updated = MatchingService.batch_warm(db, match_ids=body.match_ids, warm_level=body.warm_level)
    return ok({"updated": len(updated), "items": updated})


@router.post("/eval", summary="匹配精度评估（需求2）")
def evaluate_match(body: EvalRequest, db: Session = Depends(get_db)):
    """匹配精度评估：
    - 提供人工标注真值 reference=[{position_id, talent_id, is_match}] 时，按 (岗位,人才) 命中计算 precision/recall/F1；
    - 缺省时用自检口径：对每个岗位取 top1，统计 dimension_json 里 skill 维度 >=60 视为"合理命中"。
    """
    from app.services.matching import MatchingService
    return ok(MatchingService.evaluate(db, position_id=body.position_id, top_k=body.top_k, reference=body.reference or None))


# ==================== 状态修改（候选→推荐/录用，M-6）====================
# 注：单条改状态由上方 PUT /result/{mid}/status 提供；此处额外提供按 (岗位,人才) 改状态的入口
# 给 MatchAgent 自然语言通道使用（用户通常说"录用 XX 岗位的 YY"，没有 match_id）。

@router.post("/results/status-by-pair", summary="按 (岗位,人才) 对修改状态")
def update_match_status_by_pair(body: dict, db: Session = Depends(get_db)):
    """Agent 自然语言改状态的入口之一：知道岗位+人才编号但不知 match_id 时使用。
    鉴权沿用路由级 require_any_perm(matching:*)，与模块内其它写操作一致。
    """
    from app.services.matching import MatchingService
    if not body.get("position_id") or not body.get("talent_id"):
        raise HTTPException(400, "缺少 position_id / talent_id")
    return ok(MatchingService.update_status_by_pair(
        db, position_id=int(body["position_id"]), talent_id=int(body["talent_id"]),
        status=int(body["status"]), note=body.get("note"),
    ))


# ==================== 储备/空缺预警（M-5） ====================

@router.get("/alerts")
def list_alerts(position_id: int | None = None,
                type: str | None = Query(None, description="预警类型 reserve储备/vacancy空缺"),
                db: Session = Depends(get_db)):
    """储备/空缺预警列表（富化：岗位名/人才ID/匹配分/消息标题内容/保温等级）。"""
    rows = MatchingService.list_alerts(db, position_id=position_id, alert_type=type)
    return ok(rows)


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
    # ①事件自动触发：该岗位若存在缺口且有可补位储备 → 自动推送
    try:
        auto = MatchingService.auto_push_vacancy(db, [body.position_id])
        if auto:
            logger.info("[alerts] Agent 岗位匹配后自动推送空缺补位预警 %d 条", len(auto))
    except Exception as e:  # noqa: BLE001
        logger.warning("[alerts] Agent 岗位匹配后自动推送失败（忽略）: %s", e)
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


@router.post("/agent-match", summary="（小程序 Agent）自由文本需求 → AI拆解 + 匹配人才")
def agent_query_match(body: AgentMatchRequest, db: Session = Depends(get_db)):
    """小程序 Agent 智能匹配：输入招聘/匹配需求文本，AI 拆解为需求标签并对人才库匹配打分。

    返回：query_requirement（核心职责/必备技能/加分技能/学历/年限/软性素质）+ results（人才列表）。
    """
    data = MatchAgent.query_match(db, body.query_text, top_k=body.top_k, min_score=body.min_score)
    return ok(data)
