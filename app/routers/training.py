"""智能培训域 TR 路由（E01-E05）。权限码 training:*。"""
from fastapi import APIRouter, Depends,  Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.dao.training import CourseDAO, LessonDAO, PlanDAO, ExamDAO, ExamResultDAO
from app.schemas.training import (CourseCreate, CourseOut, CourseUpdate, ExamCreate,
                                  ExamOut, ExamSubmit, LessonCreate, LessonOut,
                                  PlanCreate, PlanOut, ProgressUpdate)
from app.services.training_agent import TrainingAgentService
from app.services.training_service import (EffectService, ExamService, PlanService,
                                           TrainingService)
from app.utils.pagination import paged_result
from app.utils.response import ok,BusinessError

router = APIRouter(dependencies=[Depends(require_permission("training:list"))])


# ---------- 课程 CRUD（E01）----------
@router.get("/courses")
def list_courses(keyword: str | None = None, category: str | None = None,
                 status: int | None = None, page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    total = CourseDAO.count(db, keyword, category, status)
    rows = CourseDAO.paged(db, keyword, category, status, page, page_size)
    return ok(paged_result([CourseOut.model_validate(c) for c in rows], page, page_size, total))


@router.post("/courses")
def create_course(body: CourseCreate, db: Session = Depends(get_db)):
    c = CourseDAO.create(db, **body.model_dump())
    db.commit()
    return ok(CourseOut.model_validate(c))


@router.put("/courses/{cid}")
def update_course(cid: int, body: CourseUpdate, db: Session = Depends(get_db)):
    c = CourseDAO.get(db, cid)
    if not c:
        raise BusinessError(404, "课程不存在")
    c = CourseDAO.update(db, c, **body.model_dump(exclude_none=True))
    db.commit()
    return ok(CourseOut.model_validate(c))


@router.delete("/courses/{cid}")
def delete_course(cid: int, db: Session = Depends(get_db)):
    c = CourseDAO.get(db, cid)
    if not c:
        raise BusinessError(404, "课程不存在")
    CourseDAO.delete(db, c)
    db.commit()
    return ok()


@router.get("/courses/{cid}/lessons")
def list_lessons(cid: int, db: Session = Depends(get_db)):
    rows = LessonDAO.list(db, LessonDAO.__model__.course_id == cid,
                          order_by=LessonDAO.__model__.sort)
    return ok([LessonOut.model_validate(l) for l in rows])


@router.post("/courses/{cid}/lessons")
def create_lesson(cid: int, body: LessonCreate, db: Session = Depends(get_db)):
    if not CourseDAO.get(db, cid):
        raise BusinessError(404, "课程不存在")
    l = LessonDAO.create(db, course_id=cid, **body.model_dump())
    db.commit()
    return ok(LessonOut.model_validate(l))


# ---------- 学习计划（E02）----------
@router.post("/plans")
def create_plan(body: PlanCreate, db: Session = Depends(get_db)):
    plan = PlanService.create(db, talent_id=body.talent_id, title=body.title,
                              course_ids=body.course_ids, deadline=body.deadline)
    db.commit()
    return ok(PlanOut.model_validate(plan))


@router.get("/plans")
def list_plans(talent_id: int | None = None, db: Session = Depends(get_db)):
    conds = []
    if talent_id:
        conds.append(PlanDAO.__model__.talent_id == talent_id)
    rows = PlanDAO.list(db, *conds, limit=500, order_by=PlanDAO.__model__.id.desc())
    return ok([PlanOut.model_validate(p) for p in rows])


@router.put("/plan/{pid}/progress")
def update_progress(pid: int, body: ProgressUpdate, db: Session = Depends(get_db)):
    if not PlanDAO.get(db, pid):
        raise BusinessError(404, "计划不存在")
    rec = PlanService.update_progress(db, plan_id=pid, talent_id=body.talent_id if hasattr(body, "talent_id") else 0,
                                      course_id=body.course_id, lesson_id=body.lesson_id,
                                      progress=body.progress)
    db.commit()
    return ok({"progress": rec.progress})


# ---------- 在线考核 / 成绩（E03）----------
@router.post("/exams")
def create_exam(body: ExamCreate, db: Session = Depends(get_db)):
    if not PlanDAO.get(db, body.plan_id):
        raise BusinessError(404, "学习计划不存在")
    e = ExamDAO.create(db, plan_id=body.plan_id, title=body.title,
                       question_ids=",".join(map(str, body.question_ids)),
                       pass_score=body.pass_score)
    db.commit()
    return ok(ExamOut.model_validate(e))


@router.post("/exam/{eid}/submit")
def submit_exam(eid: int, body: ExamSubmit, talent_id: int = Query(...),
                db: Session = Depends(get_db)):
    result = ExamService.submit(db, exam_id=eid, talent_id=talent_id, answers=body.answers)
    db.commit()
    return ok({"score": result.score, "is_pass": result.is_pass})


# ---------- Agent④ 推荐（TR-3）----------
@router.post("/agent/recommend")
def agent_recommend(body: dict, db: Session = Depends(get_db)):
    res = TrainingAgentService.generate_plan(
        db, talent_id=body["talent_id"], shortage_tags=body.get("shortage_tags", []),
        title=body.get("title", "个性化培训计划"), deadline=body.get("deadline"))
    db.commit()
    return ok(res)


# ---------- 效果分析（E05）----------
@router.get("/effects")
def effects(db: Session = Depends(get_db)):
    return ok(EffectService.overview(db))
