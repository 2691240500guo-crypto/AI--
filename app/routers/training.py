"""智能培训域 TR 路由（E01-E05）。权限码 training:*。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends,  Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_any_perm, require_client
from app.db.session import get_db
from app.dao.training import CourseDAO, LessonDAO, PlanDAO, ExamDAO, ExamResultDAO, RecordDAO
from app.models.talent import Talent
from app.models.training import Course, Lesson, ExamResult, LearningRecord, TrainingPlan
from app.models.user import User
from app.schemas.training import (AgentRecommend, CourseCreate, CourseOut,
                                  CourseUpdate, ExamCreate, ExamOut,
                                  ExamSubmit, LessonCreate, LessonOut,
                                  PlanCreate, PlanOut, PlanUpdate,
                                  ProgressUpdate, LessonSyncIn)
from app.services.training_agent import TrainingAgentService
from app.services.training_service import (EffectService, ExamService, PlanService,
                                           TrainingService)
from app.utils.pagination import paged_result
from app.utils.response import ok,BusinessError

# 权限口径：
# - 管理端（hr/admin，client_type=admin）：需持 training:course / training:plan / training:effect 之一
# - 员工端（employee，小程序 J05 在线学习）：持 training:learn 即可通过 router 级校验；
#   员工侧的数据隔离（计划只看本人、进度只能报本人）在各接口内部按 user.user_type 强制，见 list_plans / update_progress。
# 管理端写操作与统计接口额外挂 require_client("admin")，杜绝 employee token 触达（纵深防御）。
router = APIRouter(dependencies=[Depends(require_any_perm("training:course", "training:plan", "training:effect", "training:learn"))])


# ---------- 课程 CRUD（E01）----------
@router.get("/courses")
def list_courses(keyword: str | None = None, category: str | None = None,
                 status: int | None = None, page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    total = CourseDAO.count(db, keyword, category, status)
    rows = CourseDAO.paged(db, keyword, category, status, page, page_size)
    # 课节数 + 课节明细（一次 group by / 一次 in 查询，避免 N+1）
    cids = [c.id for c in rows]
    lesson_map: dict[int, list] = {}
    if cids:
        for l in db.scalars(select(Lesson).where(Lesson.course_id.in_(cids))
                             .order_by(Lesson.sort)).all():
            lesson_map.setdefault(l.course_id, []).append(l)
    items = []
    for c in rows:
        out = CourseOut.model_validate(c).model_dump()
        lessons = lesson_map.get(c.id, [])
        out["lesson_count"] = len(lessons)
        out["updated_at"] = c.updated_at
        out["lessons"] = [{"id": l.id, "title": l.title, "duration": l.duration,
                           "file_url": l.file_url} for l in lessons]
        items.append(out)
    return ok(paged_result(items, page, page_size, total))


@router.post("/courses", dependencies=[Depends(require_client("admin"))])
def create_course(body: CourseCreate, db: Session = Depends(get_db)):
    c = CourseDAO.create(db, **body.model_dump())
    db.commit()
    return ok(CourseOut.model_validate(c))


@router.put("/courses/{cid}", dependencies=[Depends(require_client("admin"))])
def update_course(cid: int, body: CourseUpdate, db: Session = Depends(get_db)):
    c = CourseDAO.get(db, cid)
    if not c:
        raise BusinessError(404, "课程不存在")
    c = CourseDAO.update(db, c, **body.model_dump(exclude_none=True))
    db.commit()
    return ok(CourseOut.model_validate(c))


@router.delete("/courses/{cid}", dependencies=[Depends(require_client("admin"))])
def delete_course(cid: int, db: Session = Depends(get_db)):
    c = CourseDAO.get(db, cid)
    if not c:
        raise BusinessError(404, "课程不存在")
    # 级联清理：学习记录（course/lesson 双外键）→ 课节 → 计划中的课程引用 → 课程
    for r in db.scalars(select(LearningRecord).where(LearningRecord.course_id == cid)).all():
        db.delete(r)
    for l in db.scalars(select(Lesson).where(Lesson.course_id == cid)).all():
        db.delete(l)
    cid_str = str(cid)
    for p in db.scalars(select(TrainingPlan)).all():
        ids = [x for x in (p.course_ids or "").split(",") if x]
        if cid_str in ids:
            p.course_ids = ",".join(x for x in ids if x != cid_str)
    CourseDAO.delete(db, c)
    db.commit()
    return ok()


@router.get("/courses/{cid}/lessons")
def list_lessons(cid: int, db: Session = Depends(get_db)):
    rows = LessonDAO.list(db, LessonDAO.__model__.course_id == cid,
                          order_by=LessonDAO.__model__.sort)
    return ok([LessonOut.model_validate(l) for l in rows])


@router.post("/courses/{cid}/lessons", dependencies=[Depends(require_client("admin"))])
def create_lesson(cid: int, body: LessonCreate, db: Session = Depends(get_db)):
    if not CourseDAO.get(db, cid):
        raise BusinessError(404, "课程不存在")
    l = LessonDAO.create(db, course_id=cid, **body.model_dump())
    db.commit()
    return ok(LessonOut.model_validate(l))


# ---------- 学习计划（E02）----------
@router.post("/plans", dependencies=[Depends(require_client("admin"))])
def create_plan(body: PlanCreate, db: Session = Depends(get_db)):
    plan = PlanService.create(db, talent_id=body.talent_id, title=body.title,
                              course_ids=body.course_ids, deadline=body.deadline,
                              weakness_tags=body.weakness_tags,
                              generated_by=body.generated_by or "manual")
    # 管理端补充字段（可选）
    if body.status is not None:
        plan.status = body.status
    if body.generated_by:
        plan.generated_by = body.generated_by
    if body.improvement is not None:
        plan.improvement = body.improvement
    db.commit()
    return ok(PlanOut.model_validate(plan))


@router.get("/plans")
def list_plans(talent_id: int | None = None, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    """计划列表：管理端可按 talent_id 查任意人；员工端（小程序 J05）强制只看本人计划。"""
    conds = []
    # 员工端强制本人：忽略前端传参，杜绝越权读取他人学习计划
    if (user.user_type or "admin") == "employee":
        if not user.talent_id:
            raise BusinessError(400, "当前账号未关联人才档案，请联系管理员")
        conds.append(PlanDAO.__model__.talent_id == user.talent_id)
    elif talent_id:
        conds.append(PlanDAO.__model__.talent_id == talent_id)
    rows = PlanDAO.list(db, *conds, limit=500, order_by=PlanDAO.__model__.id.desc())
    if not rows:
        return ok([])
    # 人才姓名映射
    tids = {p.talent_id for p in rows}
    talents = {t.id: t.name for t in db.scalars(
        select(Talent).where(Talent.id.in_(tids))).all()}
    # 学习记录映射（plan_id -> records）
    pids = [p.id for p in rows]
    records = db.scalars(
        select(LearningRecord).where(LearningRecord.plan_id.in_(pids))).all()
    rec_map: dict[int, list] = {}
    for r in records:
        rec_map.setdefault(r.plan_id, []).append(r)
    # 计划关联考试的成绩均值（exam -> plan）
    exams = db.scalars(select(ExamDAO.__model__).where(
        ExamDAO.__model__.plan_id.in_(pids))).all()
    exam_ids = [e.id for e in exams]
    exam_plan = {e.id: e.plan_id for e in exams}
    scores: dict[int, list[int]] = {}
    if exam_ids:
        for er in db.scalars(select(ExamResult).where(ExamResult.exam_id.in_(exam_ids))).all():
            scores.setdefault(exam_plan[er.exam_id], []).append(er.score)
    items = []
    for p in rows:
        out = PlanOut.model_validate(p).model_dump()
        out["talent_name"] = talents.get(p.talent_id, f"人才#{p.talent_id}")
        recs = sorted(rec_map.get(p.id, []), key=lambda r: r.course_id)
        out["records"] = [{
            "course_id": r.course_id,
            "lesson_id": r.lesson_id,
            "progress": r.progress,
            "learned_minutes": r.learned_minutes,
            "last_lesson_id": r.last_lesson_id,
            "updated_at": r.updated_at,
        } for r in recs]
        ss = scores.get(p.id, [])
        out["exam_avg"] = round(sum(ss) / len(ss)) if ss else None
        items.append(out)
    return ok(items)


@router.put("/plan/{pid}/progress")
def update_progress(pid: int, body: ProgressUpdate, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    plan = PlanDAO.get(db, pid)
    if not plan:
        raise BusinessError(404, "计划不存在")
    # 员工端仅允许上报本人的学习计划进度（防越权改写他人计划）
    if (user.user_type or "admin") == "employee":
        if not user.talent_id or plan.talent_id != user.talent_id:
            raise BusinessError(403, "只能上报本人的学习计划进度")
    # lesson_id 为 0 时自动取该课程第一节课兜底（lesson_id 有外键约束，不能存 0）
    lesson_id = body.lesson_id
    if not lesson_id:
        first = db.scalars(select(Lesson).where(Lesson.course_id == body.course_id)
                           .order_by(Lesson.sort)).first()
        if not first:
            raise BusinessError(400, "该课程暂无课节，请先在课程库中添加课件")
        lesson_id = first.id
    rec = PlanService.update_progress(db, plan_id=pid, talent_id=plan.talent_id,
                                      course_id=body.course_id, lesson_id=lesson_id,
                                      progress=body.progress,
                                      learned_minutes=body.learned_minutes)
    db.commit()
    return ok({"progress": rec.progress, "learned_minutes": rec.learned_minutes})


# ---------- 在线考核 / 成绩（E03）----------
@router.post("/exams", dependencies=[Depends(require_client("admin"))])
def create_exam(body: ExamCreate, db: Session = Depends(get_db)):
    if not PlanDAO.get(db, body.plan_id):
        raise BusinessError(404, "学习计划不存在")
    e = ExamDAO.create(db, plan_id=body.plan_id, title=body.title,
                       question_ids=",".join(map(str, body.question_ids)),
                       pass_score=body.pass_score)
    db.commit()
    return ok(ExamOut.model_validate(e))


@router.post("/exam/{eid}/submit", dependencies=[Depends(require_client("admin"))])
def submit_exam(eid: int, body: ExamSubmit, talent_id: int = Query(...),
                db: Session = Depends(get_db)):
    result = ExamService.submit(db, exam_id=eid, talent_id=talent_id, answers=body.answers)
    db.commit()
    return ok({"score": result.score, "is_pass": result.is_pass})


# ---------- Agent④ 推荐（TR-3）----------
@router.post("/agent/preview", dependencies=[Depends(require_client("admin"))])
def agent_preview(body: AgentRecommend, db: Session = Depends(get_db)):
    """智能培训 Agent 预览：读短板 + 岗位需求 → 选课，返回课程清单（不落库、不发消息）。"""
    res = TrainingAgentService.preview(
        db, talent_id=body.talent_id,
        shortage_tags=body.shortages or None,
        position_ids=body.position_ids or None,
    )
    return ok(res)


@router.post("/agent/recommend", dependencies=[Depends(require_client("admin"))])
def agent_recommend(body: AgentRecommend, db: Session = Depends(get_db)):
    """确认生成计划：按前端选定课程建计划 + 可选推送（push=False 时只建不发消息）。

    前端流程：先调 /agent/preview 选课 → 用户确认 → 调本端点（带 course_ids）落库。
    """
    res = TrainingAgentService.generate_plan(
        db, talent_id=body.talent_id,
        course_ids=body.course_ids,
        shortage_tags=body.shortages or None,
        title=body.title, deadline=body.deadline,
        push=body.push,
    )
    db.commit()
    return ok(res)



# ---------- 效果分析（E05）----------
@router.get("/effects", dependencies=[Depends(require_client("admin"))])
def effects(db: Session = Depends(get_db)):
    return ok(EffectService.overview(db))


@router.get("/effects/full", dependencies=[Depends(require_client("admin"))])
def effects_full(db: Session = Depends(get_db)):
    """效果分析全量版（培训前端 effect 页专用），原 /effects 保留给数据决策域消费。"""
    return ok(EffectService.overview_full(db))


# ---------- 以下为管理端前端对接补充端点（E01-E05 增补）----------
@router.get("/talents", dependencies=[Depends(require_client("admin"))])
def list_talents(keyword: str | None = None, db: Session = Depends(get_db)):
    """人才下拉（培训计划选择学习人员）。只读对接 tal_talent。"""
    stmt = select(Talent).where(Talent.status == 1).order_by(Talent.id.desc()).limit(500)
    if keyword:
        stmt = stmt.where(Talent.name.like(f"%{keyword}%"))
    rows = db.scalars(stmt).all()
    return ok([{"id": t.id, "name": t.name, "current_title": t.current_title}
               for t in rows])


@router.put("/plans/{pid}", dependencies=[Depends(require_client("admin"))])
def update_plan(pid: int, body: PlanUpdate, db: Session = Depends(get_db)):
    """更新计划基本信息（管理端编辑）。"""
    p = PlanDAO.get(db, pid)
    if not p:
        raise BusinessError(404, "学习计划不存在")
    if body.title is not None:
        p.title = body.title
    if body.course_ids is not None:
        p.course_ids = ",".join(map(str, body.course_ids)) if body.course_ids else ""
    if body.weakness_tags is not None:
        p.weakness_tags = ",".join(body.weakness_tags) if body.weakness_tags else ""
    if body.status is not None:
        p.status = body.status
    if body.deadline is not None:
        p.deadline = body.deadline
    if body.generated_by is not None:
        p.generated_by = body.generated_by
    if body.improvement is not None:
        p.improvement = body.improvement
    db.commit()
    return ok(PlanOut.model_validate(p))


@router.delete("/plans/{pid}", dependencies=[Depends(require_client("admin"))])
def delete_plan(pid: int, db: Session = Depends(get_db)):
    """删除计划并级联清理学习记录、关联考试及成绩。"""
    p = PlanDAO.get(db, pid)
    if not p:
        raise BusinessError(404, "学习计划不存在")
    exam_ids = [e.id for e in db.scalars(
        select(ExamDAO.__model__.id).where(ExamDAO.__model__.plan_id == pid)).all()]
    if exam_ids:
        for er in db.scalars(select(ExamResult).where(ExamResult.exam_id.in_(exam_ids))).all():
            db.delete(er)
        for e in db.scalars(select(ExamDAO.__model__).where(ExamDAO.__model__.plan_id == pid)).all():
            db.delete(e)
    for r in db.scalars(select(LearningRecord).where(LearningRecord.plan_id == pid)).all():
        db.delete(r)
    db.delete(p)
    db.commit()
    return ok()


@router.put("/courses/{cid}/lessons", dependencies=[Depends(require_client("admin"))])
def sync_lessons(cid: int, body: LessonSyncIn, db: Session = Depends(get_db)):
    """课节全量同步：带 id 的更新、无 id 的新增、缺席的删除。
    课节被学习记录引用（lesson_id 外键）时删除会报错，按业务提示。"""
    if not CourseDAO.get(db, cid):
        raise BusinessError(404, "课程不存在")
    existing = {l.id: l for l in db.scalars(
        select(Lesson).where(Lesson.course_id == cid)).all()}
    keep_ids = set()
    for idx, item in enumerate(body.lessons):
        data = item.model_dump()
        data["sort"] = idx + 1
        if data.get("id"):
            lid = data["id"]
            lesson = existing.get(lid)
            if not lesson or lesson.course_id != cid:
                raise BusinessError(400, f"课节#{lid}不属于该课程")
            for k, v in data.items():
                if k != "id":
                    setattr(lesson, k, v)
            keep_ids.add(lid)
        else:
            lesson = LessonDAO.create(db, course_id=cid, **{k: v for k, v in data.items() if k != "id"})
            keep_ids.add(lesson.id)
    for lid, lesson in existing.items():
        if lid not in keep_ids:
            db.delete(lesson)
    db.commit()
    rows = LessonDAO.list(db, Lesson.course_id == cid, order_by=Lesson.sort)
    return ok([LessonOut.model_validate(l) for l in rows])


@router.post("/plans/{pid}/push", dependencies=[Depends(require_client("admin"))])
def push_plan(pid: int, db: Session = Depends(get_db)):
    """对已生成的培训计划手动推送消息（不重建计划）。"""
    from app.services.message_service import MessageService
    from app.dao.training import PlanDAO

    plan = PlanDAO.get(db, pid)
    if not plan:
        raise BusinessError(404, "学习计划不存在")
    # 计划已推送过的话会重复发一条（消息域允许），不再做幂等；
    # 如需去重可由前端按 plan.pushed 标记判断
    MessageService.send(
        db, type_code="train", title=plan.title,
        content=f"已为你生成个性化培训计划，请点击查看并开始学习。",
        receiver_ids=[plan.talent_id], biz_type="training", biz_id=plan.id,
    )
    db.commit()
    return ok({"plan_id": plan.id, "pushed": True})
