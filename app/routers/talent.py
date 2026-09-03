#袁文武新增2026-08-31 17:10:00开始
"""人才档案路由（模块一：AI 智能人才档案与数字画像）。

接口薄：只做参数绑定、权限校验、调 service。业务编排全部在 app.services.talent_service。
权限码：读 talent:query，写 talent:manage（超管绕过）。
"""
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_client, require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.talent import (
    TalentCreate, TalentUpdate, TalentOut, TalentQuery,
    TalentProfileOut, SemanticSearchRequest, SemanticSearchHit,
    RAGRequest, RAGResponse, DedupResult, MergeRequest, GovernanceIssue,
)
from app.services import talent_service as svc
from app.services.talent_service import talent_to_out, _mask_phone
from sqlalchemy import text as sa_text


def _assert_title_in_positions(db: Session, title: str | None) -> None:
    """严格规则：人才职位（current_title）必须在岗位管理（pos_position.name）里。"""
    if not title:
        return
    exists = db.scalar(sa_text("SELECT 1 FROM pos_position WHERE name=:t LIMIT 1"),
                        {"t": title})
    if not exists:
        raise HTTPException(
            400,
            f"职位「{title}」不在岗位管理中，请先在「岗位管理」中添加该岗位，或选择已登记的职位",
        )
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter()


# ---------------- 基础 CRUD（需求① 多源入库 / ④ 查询）----------------
@router.post("", dependencies=[Depends(require_permission("talent:manage"))])
def create_talent(body: TalentCreate, db: Session = Depends(get_db),
                  current=Depends(get_current_user)):
    _assert_title_in_positions(db, body.current_title)
    return ok(svc.create_talent(db, body, operator_id=current.id))


@router.get("", dependencies=[Depends(require_permission("talent:query"))])
def list_talent(keyword: str | None = None, tag: str | None = None,
                education: str | None = None, skill: str | None = None,
                years_min: int | None = None, level: str | None = None,
                status: int | None = None, source: str | None = None,  # hq+ 前端筛选
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    # hq+ 前端兼容：status/source 筛选（在袁文武 DAO 不支持时做内存过滤）
    total = svc.TalentDAO.count(db, keyword=keyword, tag=tag, education=education,
                                skill=skill, years_min=years_min, level=level)
    rows = svc.TalentDAO.paged(db, keyword=keyword, tag=tag, education=education,
                               skill=skill, years_min=years_min, level=level,
                               page=page, page_size=page_size)
    if status is not None:
        rows = [r for r in rows if r.status == status]
    if source:
        rows = [r for r in rows if (r.resume_source or "") == source]
    talent_ids = [talent.id for talent in rows]
    account_by_talent_id: dict[int, User] = {}
    if talent_ids:
        accounts = db.scalars(
            select(User)
            .where(
                User.talent_id.in_(talent_ids),
                User.status == 1,
                User.user_type == "employee",
            )
            .order_by(User.id)
        ).all()
        # 老库若尚未应用唯一约束，稳定选取最早的有效员工账号，避免返回结果漂移。
        for account in accounts:
            account_by_talent_id.setdefault(account.talent_id, account)

    items = []
    for talent in rows:
        payload = talent_to_out(talent)
        account = account_by_talent_id.get(talent.id)
        if account:
            payload.update({
                "user_id": account.id,
                "username": account.username,
                "nickname": account.nickname,
            })
        items.append(TalentOut(**payload))
    return ok(paged_result(items, page, page_size, total))

@router.get("/governance", dependencies=[Depends(require_permission("talent:query"))])
def governance(db: Session = Depends(get_db)):
    issues = svc.governance_scan(db)
    return ok([GovernanceIssue(**i.model_dump()) for i in issues])


#袁文武新增2026-09-01 11:00:00开始 - 补充缺失接口：文本解析、批量查重、治理扫描
@router.post("/parse-text", dependencies=[Depends(require_permission("talent:manage"))])
def parse_resume_text(body: dict, db: Session = Depends(get_db),
                      current=Depends(get_current_user)):
    """文本简历智能解析入库（需求① 全格式简历智能解析）。
    直接传入简历文本，AI自动结构化并入库。"""
    resume_text = body.get("resume_text", "")
    if not resume_text or not resume_text.strip():
        raise HTTPException(400, "简历文本不能为空")
    from app.services.resume_parser import structurize
    data = structurize(resume_text)
    from app.schemas.talent import TalentCreate, EducationIn, WorkIn, ProjectIn
    from app.models.talent import Talent
    from app.services.talent_service import _coerce_text
    payload = TalentCreate(
        name=data.get("name") or "未知",
        gender=data.get("gender"), phone=data.get("phone"), email=data.get("email"),
        highest_education=data.get("highest_education"), major=data.get("major"),
        current_title=data.get("current_title"),
        years_experience=int(data.get("years_experience") or 0),
        salary_expectation=data.get("salary_expectation"),
        skills=_coerce_text(data.get("skills")),
        work_experience=_coerce_text(data.get("work_experience")),
        project_experience=_coerce_text(data.get("project_experience")),
        honors=_coerce_text(data.get("honors")),
        resume_source="text",
        educations=[EducationIn(**e) for e in (data.get("educations") or [])],
        works=[WorkIn(**w) for w in (data.get("works") or [])],
        projects=[ProjectIn(**p) for p in (data.get("projects") or [])],
        tag_names=data.get("tags", []),
    )
    t = Talent(**payload.model_dump(exclude={"educations": True, "works": True, "projects": True, "tag_names": True}))
    t.created_by = current.id
    db.add(t)
    db.flush()
    # 子表
    if payload.educations:
        from app.models.talent import TalentEducation
        for e in payload.educations:
            db.add(TalentEducation(talent_id=t.id, **e.model_dump()))
    if payload.works:
        from app.models.talent import TalentWorkExperience
        for w in payload.works:
            db.add(TalentWorkExperience(talent_id=t.id, **w.model_dump()))
    if payload.projects:
        from app.models.talent import TalentProject
        for p in payload.projects:
            db.add(TalentProject(talent_id=t.id, **p.model_dump()))
    # 标签
    if payload.tag_names:
        from app.dao.talent import TagDAO, TalentTagRelDAO
        tags = TagDAO.ensure_tags(db, payload.tag_names, category="custom", source="ai")
        TalentTagRelDAO.set_ai_tags(db, t.id, [tg.id for tg in tags])
    db.commit()
    db.refresh(t)
    # 返回完整的人才详情（含标签、脱敏信息）
    from app.services.talent_service import talent_to_out
    result = talent_to_out(t)
    result["parsed_fields"] = list(data.keys())
    return ok(result)


@router.post("/deduplicate/check", dependencies=[Depends(require_permission("talent:query"))])
def deduplicate_check(db: Session = Depends(get_db)):
    """全量查重检测（需求③ 智能查重与数据治理）。
    扫描全部人才档案，返回所有重复候选组。"""
    from sqlalchemy import select, or_
    from app.models.talent import Talent
    # 基于手机号/姓名+生日等维度查重
    talents = db.query(Talent).filter(Talent.status == 1).all()
    dup_groups = []
    # 手机号查重
    phone_map = {}
    for t in talents:
        if t.phone and t.phone.strip():
            key = t.phone.strip()
            phone_map.setdefault(key, []).append(t)
    for phone, group in phone_map.items():
        if len(group) > 1:
            dup_groups.append({
                "type": "phone", "key": phone,
                "talents": [{"id": t.id, "name": t.name, "phone": t.phone} for t in group]
            })
    # 姓名+学历查重
    name_edu_map = {}
    for t in talents:
        if t.name and t.highest_education:
            key = f"{t.name}|{t.highest_education}"
            name_edu_map.setdefault(key, []).append(t)
    for key, group in name_edu_map.items():
        if len(group) > 1:
            dup_groups.append({
                "type": "name_education", "key": key,
                "talents": [{"id": t.id, "name": t.name, "education": t.highest_education} for t in group]
            })
    return ok({
        "total_groups": len(dup_groups),
        "total_duplicates": sum(len(g["talents"]) for g in dup_groups),
        "groups": dup_groups[:50],  # 最多返回50组
    })


@router.post("/governance/scan", dependencies=[Depends(require_permission("talent:manage"))])
def governance_scan_post(db: Session = Depends(get_db)):
    """数据治理扫描（POST触发，需求③ 智能查重与数据治理）。
    扫描全量档案，识别缺失/错误/质量问题，返回问题清单。"""
    issues = svc.governance_scan(db)
    # 按问题类型分类统计（GovernanceIssue 无 level 字段，用 issue_type 替代）
    missing = sum(1 for i in issues if i.issue_type == "missing_field")
    dup = sum(1 for i in issues if i.issue_type == "duplicate")
    error = sum(1 for i in issues if i.issue_type == "error")
    return ok({
        "total": len(issues),
        "by_type": {
            "missing_field": missing,
            "duplicate": dup,
            "error": error,
            "suspect": sum(1 for i in issues if i.issue_type == "suspect"),
        },
        "issues": [i.model_dump() for i in issues],
    })


@router.post("/governance/repair", dependencies=[Depends(require_permission("talent:manage"))])
def governance_repair_post(body: dict | None = None, db: Session = Depends(get_db)):
    """hq+ 2026-09-01 一键标准化整改：自动修复学历/性别/手机号/邮箱/证件号/年限等
    机器可判定的不规范项（幂等）。body: {"talent_ids": [1,2]}（缺省=全部在档）。"""
    from app.utils.response import ok as _ok
    body = body or {}
    ids = body.get("talent_ids")
    result = svc.governance_repair(db, talent_ids=ids)
    db.commit()
    return _ok(result)
#袁文武新增2026-09-01 11:00:00结束


#袁文武新增2026-08-31 22:00:00开始
# 需求④ 优化补全：Excel 批量导入 / 多维统计 / 档案导出 / 过期提醒。
# 注意：静态路径必须声明在 /{tid} 之前，避免被路径参数路由抢匹配。

@router.post("/import-excel", dependencies=[Depends(require_permission("talent:manage"))])
async def import_excel(file: UploadFile = File(...), db: Session = Depends(get_db),
                       current=Depends(get_current_user)):
    """Excel 批量导入人才（.xlsx）。表头支持：姓名/性别/手机号/邮箱/学历/专业/职位/年限/薪资期望/技能/工作经历/项目经验/荣誉/标签。"""
    content = await file.read()
    return ok(svc.import_excel_talents(db, content, filename=file.filename or "talents.xlsx",
                                       operator_id=current.id))





@router.get("/stats", dependencies=[Depends(require_permission("talent:query"))])
def stats(db: Session = Depends(get_db)):
    """多维查询统计：学历/能力等级/技能/来源分布 + 过期计数。"""
    return ok(svc.talent_stats(db))





@router.get("/expiring", dependencies=[Depends(require_permission("talent:query"))])
def expiring(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    """过期信息提醒：expire_at 距今 <=days 天（含已过期）的档案。"""
    return ok(svc.scan_expiring(db, days=days))





@router.get("/export", dependencies=[Depends(require_permission("talent:query"))])
def export_talents(keyword: str | None = None, tag: str | None = None,
                   education: str | None = None, skill: str | None = None,
                   years_min: int | None = None, level: str | None = None,
                   status: int | None = None, source: str | None = None,
                   db: Session = Depends(get_db)):
    """档案一键导出（.xlsx，含标签列，支持多维筛选条件，满足需求④ 导出/备份/打印）。"""
    import io
    import logging
    from datetime import datetime
    from fastapi.responses import StreamingResponse
    import openpyxl

    logger = logging.getLogger(__name__)
    try:
        # 按筛选条件取数：有筛选条件走分页查询拉全量，否则走 list_all_valid
        has_filter = any([keyword, tag, education, skill, years_min, level,
                          status is not None, source])
        if has_filter:
            total = svc.TalentDAO.count(db, keyword=keyword, tag=tag, education=education,
                                        skill=skill, years_min=years_min, level=level,
                                        only_valid=(status != 0))
            rows = []
            page_size = 500
            for p in range(1, (total // page_size) + 2):
                batch = svc.TalentDAO.paged(db, keyword=keyword, tag=tag, education=education,
                                            skill=skill, years_min=years_min, level=level,
                                            page=p, page_size=page_size,
                                            only_valid=(status != 0))
                rows.extend(batch)
                if len(batch) < page_size:
                    break
            # 内存过滤 status / source（DAO 暂不原生支持）
            if status is not None:
                rows = [r for r in rows if r.status == status]
            if source:
                rows = [r for r in rows if (r.resume_source or "") == source]
        else:
            rows = svc.TalentDAO.list_all_valid(db, limit=10000)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "人才档案"
        ws.append(["ID", "姓名", "性别", "手机号(脱敏)", "邮箱", "最高学历", "专业", "当前职位",
                   "从业年限", "薪资期望", "技能", "工作经历", "项目经验", "荣誉资质",
                   "标签", "数据质量", "入库来源", "建档时间"])
        # Excel 单单元格字符上限 32767，超长内容截断
        MAX_CELL_LEN = 32000
        def _trunc(s):
            s = str(s) if s is not None else ""
            return s[:MAX_CELL_LEN] if len(s) > MAX_CELL_LEN else s

        for t in rows:
            try:
                tag_str = ""
                if t.tag_rels:
                    tag_str = "、".join(r.tag.name for r in t.tag_rels if r and r.tag)
                ws.append([
                    t.id, _trunc(t.name), _trunc(t.gender), _mask_phone(t.phone), _trunc(t.email),
                    _trunc(t.highest_education), _trunc(t.major), _trunc(t.current_title),
                    t.years_experience or 0, _trunc(t.salary_expectation), _trunc(t.skills),
                    _trunc(t.work_experience), _trunc(t.project_experience), _trunc(t.honors),
                    _trunc(tag_str),
                    _trunc(t.data_quality), _trunc(t.resume_source),
                    t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
                ])
            except Exception as e:
                logger.warning(f"导出时跳过人才 {t.id}: {e}")
                continue

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        fname = f"talent_export_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        return StreamingResponse(
            buf,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={fname}"})
    except Exception as e:
        logger.exception(f"导出人才档案失败: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")
#袁文武新增2026-08-31 22:00:00结束



@router.post("/parse", dependencies=[Depends(require_permission("talent:manage"))])
async def parse_resume(file: UploadFile = File(...), db: Session = Depends(get_db),
                       current=Depends(get_current_user)):
    content = await file.read()
    return ok(svc.parse_resume_file(db, file.filename or "resume", content,
                                    operator_id=current.id))





@router.post("/parse-batch", dependencies=[Depends(require_permission("talent:manage"))])
async def parse_resume_batch(files: list[UploadFile] = File(...),
                             db: Session = Depends(get_db),
                             current=Depends(get_current_user)):
    results = []
    for f in files:
        content = await f.read()
        try:
            results.append({"file": f.filename, "ok": True,
                            "data": svc.parse_resume_file(db, f.filename or "resume",
                                                          content, operator_id=current.id)})
        except Exception as e:  # 单文件失败不影响整体
            results.append({"file": f.filename, "ok": False, "error": str(e)})
    return ok(results)


# ---------------- 需求② 向量级人才画像 ----------------



@router.post("/merge", dependencies=[Depends(require_permission("talent:manage"))])
def merge(body: MergeRequest, db: Session = Depends(get_db)):
    return ok(svc.merge_talents(db, body.primary_id, body.duplicate_ids))


# ---------------- 需求④ 语义化人才检索 ----------------

@router.post("/search", dependencies=[Depends(require_permission("talent:query"))])
def search(body: SemanticSearchRequest, db: Session = Depends(get_db)):
    hits = svc.semantic_search(db, body.query, top_k=body.top_k, use_vector=body.use_vector)
    return ok([SemanticSearchHit(**h.model_dump()) for h in hits])


# 袁文武 2026-09-03：语义搜索 v2，返回完整解析信息、匹配条件等
@router.post("/search-v2", dependencies=[Depends(require_permission("talent:query"))])
def search_v2(body: SemanticSearchRequest, db: Session = Depends(get_db)):
    """语义搜索 v2：NLU 解析 + 结构化过滤 + 向量精排 + 匹配解释。"""
    from app.services.talent_service import semantic_search_v2
    result = semantic_search_v2(
        db, query=body.query, top_k=body.top_k, use_vector=body.use_vector,
    )
    return ok(result)


# ---------------- 需求⑤ 档案 RAG 问答 ----------------



@router.post("/{talent_id}/portrait", dependencies=[Depends(require_permission("talent:manage"))])
def generate_portrait(talent_id: int, db: Session = Depends(get_db)):
    """生成AI数字画像（需求② 向量级人才画像）。
    生成AI标签、技能/经验/素质三维向量、潜力评级。"""
    from app.services.talent_service import build_profile, TalentDAO
    from app.utils.response import BusinessError
    t = TalentDAO.get(db, talent_id)
    if not t:
        raise BusinessError(404, "人才不存在")
    profile = build_profile(db, t, fast=False)
    db.commit()
    return ok(profile.model_dump())

@router.post("/rag", dependencies=[Depends(require_permission("talent:query"))])
def rag(body: RAGRequest, db: Session = Depends(get_db)):
    # 兼容 talent_id（单人才）和 talent_ids（批量）
    ids = body.talent_ids
    if body.talent_id:
        ids = [body.talent_id]
    scope = body.scope
    if body.talent_id and scope == "batch":
        scope = "single"  # 单人才自动设为 single
    resp = svc.rag_ask(db, body.question, talent_ids=ids,
                       top_k=body.top_k, scope=scope)
    return ok(resp)


# ---------------- 内置标签库 ----------------

@router.post("/tags/seed", dependencies=[Depends(require_permission("talent:manage"))])
def seed_tags(db: Session = Depends(get_db)):
    added = svc.seed_builtin_tags(db)
    db.commit()
    return ok({"added": added, "total_builtin": len(svc.SEED_TAGS)})
#袁文武新增2026-08-31 17:10:00结束

#袁文武新增2026-08-31 20:55:00开始
# 独立"上传简历原文件"接口：仅将简历文件存到对象存储(MinIO)，不触发 AI 解析，
# 与 /parse(上传+解析一步到位) 区分。对象名格式与 parse_resume_file 保持一致。

@router.post("/upload", dependencies=[Depends(require_permission("talent:manage"))])
async def upload_resume(file: UploadFile = File(...), current=Depends(get_current_user)):
    import uuid
    from datetime import datetime
    from app.core.config import get_settings
    content = await file.read()
    object_name = f"resumes/{datetime.now():%Y/%m}/{uuid.uuid4().hex}_{file.filename or 'resume'}"
    try:
        from app.utils.object_storage import get_object_storage
        store = get_object_storage()
        store.put_bytes(object_name, content, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(500, f"简历文件上传失败（请确认 MinIO 已就绪）：{e}")
    return ok({
        "object_name": object_name,
        "filename": file.filename,
        "size": len(content),
        "bucket": get_settings().MINIO_BUCKET,
    })
#袁文武新增2026-08-31 20:55:00结束

#袁文武新增2026-08-31 23:30:00开始
# ---------------- 标签管理（需求② 自定义标签分类管理）----------------

@router.get("/tags", dependencies=[Depends(require_permission("talent:query"))])
def list_tags(keyword: str | None = None, category: str | None = None,
              is_builtin: int | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
              db: Session = Depends(get_db)):
    from app.schemas.talent import TagOut
    rows, total = svc.list_tags(db, keyword=keyword, category=category,
                                 is_builtin=is_builtin, page=page, page_size=page_size)
    items = [TagOut(id=t.id, name=t.name, category=t.category,
                    description=t.description, is_builtin=t.is_builtin) for t in rows]
    return ok(paged_result(items, page, page_size, total))





@router.get("/tags/categories", dependencies=[Depends(require_permission("talent:query"))])
def tag_categories(db: Session = Depends(get_db)):
    return ok(svc.list_tag_categories(db))





@router.post("/tags", dependencies=[Depends(require_permission("talent:manage"))])
def create_tag(body: dict, db: Session = Depends(get_db)):
    from app.schemas.talent import TagOut, TagCreate
    payload = TagCreate(**body)
    tag = svc.create_tag(db, payload.name, payload.category, payload.description)
    return ok(TagOut(id=tag.id, name=tag.name, category=tag.category,
                     description=tag.description, is_builtin=tag.is_builtin))



@router.post("/import-word", dependencies=[Depends(require_permission("talent:manage"))])
async def import_word(file: UploadFile = File(...), db: Session = Depends(get_db),
                      current=Depends(get_current_user)):
    """Word 批量导入人才（.docx）。支持表格形式或键值对段落形式。"""
    content = await file.read()
    return ok(svc.import_word_talents(db, content, filename=file.filename or "talents.docx",
                                       operator_id=current.id))


# ---------------- 员工端（小程序）：本人档案（数据隔离锚点）----------------
# 注意：静态路径必须注册在 /{tid} 动态路由之前，否则被当作 tid 解析
@router.get("/me", summary="我的档案（员工端，仅本人）")
def my_talent(db: Session = Depends(get_db),
              user=Depends(require_client("app"))):
    """员工小程序查看本人档案：从 token 关联的 talent_id 读取，强制本人，不接受前端传参。"""
    from app.services.talent_service import _to_out
    from app.models.talent import Talent
    if not user.talent_id:
        raise HTTPException(400, "当前账号未关联人才档案，请联系管理员")
    t = db.get(Talent, user.talent_id)
    if not t:
        raise HTTPException(404, "人才档案不存在")
    return ok(_to_out(t))


# ---------------- 技能证书管理（需求① 技能证书核心信息）----------------


#袁文武新增2026-09-01 00:30:00开始 - 路由顺序修复（静态路径优先）
@router.get("/{tid}", dependencies=[Depends(require_permission("talent:query"))])
def get_talent(tid: int, db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    return ok(TalentOut(**talent_to_out(t)))





@router.put("/{tid}", dependencies=[Depends(require_permission("talent:manage"))])
def update_talent(tid: int, body: TalentUpdate, db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    data = body.model_dump(exclude_unset=True)
    tag_names = data.pop("tag_names", None)
    # 严格规则：若更新带职位，必须在岗位管理中
    _assert_title_in_positions(db, data.get("current_title"))
    for k, v in data.items():
        if v is not None:
            setattr(t, k, v)
    if tag_names is not None:
        from app.dao.talent import TagDAO
        from app.models.talent import TalentTalentTag
        tags = TagDAO.ensure_tags(db, tag_names, category="custom", source="manual")
        # 先清手动标签，再写（AI 自动标签保留）
        db.execute(TalentTalentTag.__table__.delete()
                   .where(TalentTalentTag.talent_id == tid, TalentTalentTag.source == "manual"))
        for tag in tags:
            db.add(TalentTalentTag(talent_id=tid, tag_id=tag.id, source="manual"))
    db.commit()
    db.refresh(t)
    # hq+ 2026-09-01：编辑保存后动态刷新四维向量（含简历原文维），画像实时更新
    try:
        from app.services.talent_vector_service import upsert_talent_vectors  # hq+
        upsert_talent_vectors(t)
    except Exception as e:
        import logging
        logging.getLogger("hq").warning("编辑保存后向量刷新失败（不影响保存）：%s", e)
    return ok(TalentOut(**talent_to_out(t)))





@router.delete("/{tid}", dependencies=[Depends(require_permission("talent:manage"))])
def delete_talent(tid: int, db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    db.delete(t)
    db.commit()
    return ok()


# ---------------- 需求① 全格式简历智能解析 ----------------

@router.post("/{tid}/profile", dependencies=[Depends(require_permission("talent:manage"))])
def rebuild_profile(tid: int, db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    profile = svc.build_profile(db, t)
    db.commit()
    return ok(profile)


# ---------------- 需求③ 智能查重与数据治理 ----------------

@router.get("/{tid}/duplicates", dependencies=[Depends(require_permission("talent:query"))])
def talent_duplicates(tid: int, db: Session = Depends(get_db)):
    return ok(svc.find_duplicates(db, tid).model_dump())





@router.put("/tags/{tag_id}", dependencies=[Depends(require_permission("talent:manage"))])
def update_tag(tag_id: int, body: dict, db: Session = Depends(get_db)):
    from app.schemas.talent import TagOut, TagUpdate
    payload = TagUpdate(**body)
    tag = svc.update_tag(db, tag_id, name=payload.name, category=payload.category,
                         description=payload.description)
    return ok(TagOut(id=tag.id, name=tag.name, category=tag.category,
                     description=tag.description, is_builtin=tag.is_builtin))





@router.delete("/tags/{tag_id}", dependencies=[Depends(require_permission("talent:manage"))])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    svc.delete_tag(db, tag_id)
    return ok()


# ---------------- Word 批量导入（需求① 多源入库 · Word）----------------

@router.get("/{tid}/certificates", dependencies=[Depends(require_permission("talent:query"))])
def list_certificates(tid: int, db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    return ok(svc.list_certificates(db, tid))





@router.put("/{tid}/certificates", dependencies=[Depends(require_permission("talent:manage"))])
def save_certificates(tid: int, body: list[dict], db: Session = Depends(get_db)):
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    svc.save_certificates(db, tid, body)
    return ok(svc.list_certificates(db, tid))


# ---------------- 打印模板（需求④ 打印）----------------

@router.get("/{tid}/print", dependencies=[Depends(require_permission("talent:query"))])
def print_talent(tid: int, db: Session = Depends(get_db)):
    """返回人才档案的打印版 HTML（可直接浏览器打印 / 另存为 PDF）。"""
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    data = talent_to_out(t)
    certs = svc.list_certificates(db, tid)
    html = _render_print_html(data, certs)
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html)


def _render_print_html(data: dict, certs: list[dict]) -> str:
    tag_html = ''.join(f'<span class="tag">{t["name"]}</span>' for t in data.get("tags", []))
    edu_rows = ''.join(
        f'<tr><td>{e["school"] or ""}</td><td>{e["degree"] or ""}</td>'
        f'<td>{e["major"] or ""}</td><td>{e["start_year"] or ""} - {e["end_year"] or ""}</td></tr>'
        for e in data.get("educations", []))
    work_rows = ''.join(
        f'<tr><td>{w["company"] or ""}</td><td>{w["title"] or ""}</td>'
        f'<td>{w["start_date"] or ""} - {w["end_date"] or ""}</td>'
        f'<td>{w["description"] or ""}</td></tr>'
        for w in data.get("works", []))
    proj_rows = ''.join(
        f'<tr><td>{p["name"] or ""}</td><td>{p["role"] or ""}</td>'
        f'<td>{p["description"] or ""}</td></tr>'
        for p in data.get("projects", []))
    cert_rows = ''.join(
        f'<tr><td>{c["name"] or ""}</td><td>{c["issuer"] or ""}</td>'
        f'<td>{c["level"] or ""}</td><td>{c["issue_date"] or ""}</td>'
        f'<td>{c["expire_date"] or ""}</td></tr>'
        for c in certs)
    return f'''<!DOCTYPE html><html><head><meta charset="utf-8"><title>人才档案 - {data["name"]}</title>
<style>
body {{ font-family: "Microsoft YaHei", sans-serif; margin: 30px; color: #333; }}
h1 {{ text-align: center; font-size: 22px; border-bottom: 2px solid #333; padding-bottom: 10px; }}
h2 {{ font-size: 16px; border-left: 4px solid #409eff; padding-left: 8px; margin-top: 20px; }}
.info-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px 20px; margin: 12px 0; }}
.info-item {{ font-size: 14px; }}
.info-item b {{ color: #666; font-weight: normal; }}
table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
th {{ background: #f5f7fa; font-weight: 600; }}
.tag {{ display: inline-block; padding: 2px 10px; margin: 2px; background: #ecf5ff;
       border: 1px solid #d9ecff; border-radius: 4px; font-size: 12px; color: #409eff; }}
.footer {{ margin-top: 30px; text-align: right; font-size: 12px; color: #999; }}
@media print {{ body {{ margin: 15px; }} }}
</style></head><body>
<h1>人才档案表</h1>
<div class="info-grid">
  <div class="info-item"><b>姓名：</b>{data["name"]}</div>
  <div class="info-item"><b>性别：</b>{data.get("gender") or "-"}</div>
  <div class="info-item"><b>手机号：</b>{data.get("phone_masked") or "-"}</div>
  <div class="info-item"><b>邮箱：</b>{data.get("email") or "-"}</div>
  <div class="info-item"><b>最高学历：</b>{data.get("highest_education") or "-"}</div>
  <div class="info-item"><b>专业：</b>{data.get("major") or "-"}</div>
  <div class="info-item"><b>当前职位：</b>{data.get("current_title") or "-"}</div>
  <div class="info-item"><b>从业年限：</b>{data.get("years_experience", 0)} 年</div>
  <div class="info-item"><b>薪资期望：</b>{data.get("salary_expectation") or "-"}</div>
  <div class="info-item"><b>数据质量：</b>{data.get("data_quality") or "-"}</div>
</div>
<h2>标签画像</h2>
<div>{tag_html or "-"}</div>
<h2>教育经历</h2>
<table><tr><th>学校</th><th>学历</th><th>专业</th><th>时间</th></tr>{edu_rows or "<tr><td colspan=4>-</td></tr>"}</table>
<h2>工作经历</h2>
<table><tr><th>公司</th><th>职位</th><th>时间</th><th>描述</th></tr>{work_rows or "<tr><td colspan=4>-</td></tr>"}</table>
<h2>项目经验</h2>
<table><tr><th>项目名称</th><th>角色</th><th>描述</th></tr>{proj_rows or "<tr><td colspan=3>-</td></tr>"}</table>
<h2>技能证书</h2>
<table><tr><th>证书名称</th><th>颁发机构</th><th>等级</th><th>颁发日期</th><th>到期日期</th></tr>{cert_rows or "<tr><td colspan=5>-</td></tr>"}</table>
<h2>技能与资质</h2>
<p><b>核心技能：</b>{data.get("skills") or "-"}</p>
<p><b>荣誉资质：</b>{data.get("honors") or "-"}</p>
<div class="footer">建档时间：{str(data.get("created_at", ""))[:19]}</div>
</body></html>'''
#袁文武新增2026-08-31 23:30:00结束
#袁文武新增2026-09-01 00:30:00结束




# ============ hq+  批次1/2.3/批次C：附件简历 / 向量视图 / 覆盖合并 / AI报告（在袁文武功能基础上补充）============
@router.get("/{tid}/resume", summary="附件简历流式返回（?inline=1 内联预览）", include_in_schema=True)
async def download_resume(
    tid: int,
    inline: int = Query(0, description="1=内联预览 0=附件下载"),
    db: Session = Depends(get_db),
):
    """从 MinIO / 本地取原始简历文件字节（hq+ 附件简历下载/预览）。
    - 修改人：袁文武  修改时间：2026-09-02
    - 优化：补充 resume_id 字段检查、MinIO 失败时本地文件兜底、动态 content-type。"""
    from fastapi.responses import Response
    import os
    import mimetypes
    from pathlib import Path
    from app.utils.object_storage import get_object_storage

    obj = svc.TalentDAO.get(db, tid)
    if not obj:
        raise HTTPException(404, "人才档案不存在")

    # 依次检查三个可能的 MinIO 键字段
    key = obj.object_key or obj.resume_file or obj.resume_id
    if not key:
        raise HTTPException(404, "该档案没有附件简历")

    # 从 key 提取文件名推断 content-type 和下载扩展名
    raw_filename = (key or "").rsplit("/", 1)[-1] if "/" in (key or "") else (key or "resume")
    ext = raw_filename.rsplit(".", 1)[-1].lower() if "." in raw_filename else "pdf"
    mime_type, _ = mimetypes.guess_type(raw_filename)
    if not mime_type:
        _mime_map = {
            "pdf": "application/pdf", "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "webp": "image/webp",
        }
        mime_type = _mime_map.get(ext, "application/octet-stream")

    data: bytes | None = None
    last_error: str | None = None

    # 策略1：MinIO 读取
    try:
        data = get_object_storage().get_bytes(key)
    except Exception as e:
        last_error = str(e)

    # 策略2：MinIO 失败时，尝试本地文件兜底
    if data is None:
        local_dirs = [
            Path("uploads/resumes"),
            Path("uploads"),
            Path("."),
        ]
        for base in local_dirs:
            # 尝试文件名匹配
            candidate = base / raw_filename
            if candidate.is_file():
                try:
                    data = candidate.read_bytes()
                    last_error = None
                    break
                except Exception:
                    continue
            # 尝试完整路径匹配
            candidate2 = base / key
            if candidate2.is_file():
                try:
                    data = candidate2.read_bytes()
                    last_error = None
                    break
                except Exception:
                    continue

    if data is None:
        detail = "简历读取失败"
        if last_error:
            detail += f"（MinIO: {last_error[:100]}）"
        raise HTTPException(500, detail)

    fname = f"resume_{tid}.{ext}"
    disposition = "inline" if inline else f'attachment; filename="{fname}"'
    return Response(content=data, media_type=mime_type,
                    headers={"Content-Disposition": disposition,
                             "Content-Length": str(len(data))})

@router.get("/{tid}/vectors", summary="查看人才三维向量画像（text 预览）")
def talent_vectors(tid: int, db: Session = Depends(get_db)):
    """hq+ 批次2.3c：查看某人才三维向量（技能/经验/素质）是否有值。"""
    from app.services.talent_vector_service import get_talent_vectors  # hq+
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    return ok(get_talent_vectors(tid, talent=t))


# 袁文武 2026-09-03：获取人才画像概览（从已有标签+报告读取，不重新生成）
@router.get("/{tid}/profile/overview", summary="获取人才画像概览")
def get_profile(tid: int, db: Session = Depends(get_db)):
    """获取人才画像：8 维度标签分组 + 元信息。从已有数据读取，不触发 AI 生成。"""
    from app.models.talent import TalentTalentTag, TalentTag
    from app.services.talent_service import TAG_DIM_LABELS, SEED_TAGS
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")

    # 从标签关系表读取 AI 生成的标签
    rels = (db.query(TalentTag.name, TalentTag.category, TalentTalentTag.score)
            .join(TalentTag, TalentTag.id == TalentTalentTag.tag_id)
            .filter(TalentTalentTag.talent_id == tid)
            .order_by(TalentTalentTag.score.desc())
            .all())

    tags_by_dim = {dim: [] for dim in TAG_DIM_LABELS}
    all_tags = []
    for name, category, score in rels:
        if category and category in tags_by_dim:
            tags_by_dim[category].append(name)
        all_tags.append(name)

    # 潜力评级（从 potential 维度取第一个）
    potential = tags_by_dim.get("potential", [None])[0] if tags_by_dim.get("potential") else None

    return ok({
        "talent_id": tid,
        "name": t.name,
        "ai_tags": all_tags,
        "tags_by_dim": tags_by_dim,
        "tag_count": len(all_tags),
        "potential_level": potential,
        "skill_summary": t.skills,
        "experience_summary": t.work_experience,
        "quality_summary": None,
        "vectors_built": False,  # 概览接口不查向量状态
        "generate_mode": "cached",
        "profile_updated_at": t.updated_at.strftime("%Y-%m-%d %H:%M:%S") if t.updated_at else None,
    })


@router.post("/merge-overwrite", summary="上传弹框确认：用新简历覆盖旧档案")
def merge_overwrite(
    new_id: int = Query(..., description="新上传档案 id"),
    old_id: int = Query(..., description="疑似重复旧档案 id"),
    db: Session = Depends(get_db),
):
    """hq+ 批次C：上传简历命中重复后，前端弹框确认覆盖。"""
    from app.services.talent_dedup_service import TalentDedupService  # hq+
    obj = TalentDedupService.overwrite(db, new_id, old_id, remark="上传弹框人工确认覆盖")
    db.commit()
    return ok({"talent_id": obj.id, "message": "已用新简历覆盖旧档案"})


@router.get("/{tid}/report", summary="获取 AI 解析报告")
def get_talent_report(tid: int, db: Session = Depends(get_db)):
    """hq+ 批次2.3b：读 tal_talent_report 的 summary_report / parsed_json。

    hq+ 2026-09-01 修复：skills/highlights/shortcomings/fit_positions 在 DB 里是 JSON 字符串
    （存储选择），这里解析回 list 返给前端，避免 v-for 误迭代字符串产生单字符 chip。
    """
    import json
    from app.dao.talent_report import TalentReportDAO  # hq+
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    report = TalentReportDAO.get_by(db, talent_id=tid)
    if not report:
        return ok({"talent_id": tid, "has_report": False})

    def _loads(v):
        if isinstance(v, (list, dict)):
            return v
        if not v:
            return []
        try:
            return json.loads(v)
        except Exception:
            return []

    return ok({
        "talent_id": tid,
        "has_report": True,
        "summary_report": report.summary_report,
        "skills": _loads(report.skills),
        "highlights": _loads(report.highlights),
        "shortcomings": _loads(report.shortcomings),
        "fit_positions": _loads(report.fit_positions),
        "potential": report.potential,
        # 袁文武 2026-09-02：AI 解析新增三大板块
        "ability_level": getattr(report, "ability_level", None),
        "experience_summary": getattr(report, "experience_summary", None),
        "composite_score": getattr(report, "composite_score", None),
        "parsed_json": report.parsed_json,
    })


@router.post("/{tid}/reparse", summary="重新跑 LLM 解析（写入主档空字段）")
def reparse_talent(tid: int, db: Session = Depends(get_db)):
    """hq+ 批次2.3b：手动重跑 LLM 解析（用简历原文，只填空字段 + 覆盖 AI 报告）。"""
    from app.services.resume_llm_service import ResumeLLMService  # hq+
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    text = t.resume_text or t.summary or ""
    if not text.strip():
        raise HTTPException(400, "该人才没有简历原文，无法重跑")
    try:
        result = ResumeLLMService.apply(db, t, text)
        db.commit()
        # hq+  2026-09-01：重跑后刷新四维向量（含简历原文维）
        try:
            from app.services.talent_vector_service import upsert_talent_vectors  # hq+
            upsert_talent_vectors(t)
        except Exception as ve:
            import logging
            logging.getLogger("hq").warning("重跑后向量化失败：%s", ve)
        return ok({"talent_id": tid, "message": "解析完成", "new_tags": result.get("new_tag_count", 0)})
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"重跑解析失败：{e}") from e



# ============ hq+  人才标签绑定接口（我的 edit.vue 依赖；袁文武 TalentOut 已嵌套 tags，这里补充独立 CRUD）============
@router.get("/{tid}/tags", summary="获取某人才的标签列表")
def talent_tags_list(tid: int, db: Session = Depends(get_db),
                     user=Depends(require_permission("talent:query"))):
    """返回 [{id, tag_id, name, category, source, score}]（兼容我的 edit.vue boundDictIds）。"""
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    items = []
    for rel in t.tag_rels:
        if not rel.tag:
            continue
        items.append({
            "id": rel.tag_id,
            "tag_id": rel.tag_id,
            "name": rel.tag.name,
            "category": rel.tag.category,
            "source": rel.source,
            "score": rel.score,
        })
    return ok(items)


@router.put("/{tid}/tags", summary="覆盖式绑定人才标签")
def talent_tags_bind(tid: int, body: dict, db: Session = Depends(get_db),
                     user=Depends(require_permission("talent:manage"))):
    """body: { tag_ids: [1,2,3], source: 'manual' } —— 全量覆盖式绑定（清掉不在集合内的所有关联）。"""
    from app.models.talent import TalentTalentTag  # hq+
    t = svc.TalentDAO.get(db, tid)
    if not t:
        raise HTTPException(404, "人才不存在")
    tag_ids = [int(x) for x in (body.get("tag_ids") or [])]
    source = body.get("source") or "manual"
    # 全量覆盖：删旧建新
    for rel in list(t.tag_rels):
        db.delete(rel)
    db.flush()
    for tag_id in tag_ids:
        db.add(TalentTalentTag(talent_id=tid, tag_id=tag_id, source=source))
    db.commit()
    return ok({"message": "标签已更新", "count": len(tag_ids)})
