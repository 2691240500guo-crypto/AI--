"""智能测评域路由：题库 / 题目 / 试卷 / 发起 / 作答 / 判分 / 报告。
对齐 01-需求分析 4.3 接口。
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.dao.assessment import (
    PaperDAO, QuestionBankDAO, QuestionDAO, ResultDAO,
)
from app.db.session import get_db
from app.models.assessment import (
    Paper, Question, QuestionBank, Result, ResultDetail,
)
from app.models.talent import Talent
from app.schemas.assessment import (
    AnswerItem, AnswerViewOut, AnswerViewQuestion, LaunchRequest, LaunchResponse,
    LaunchResultItem, PaperAutoCreate, PaperCreate, PaperDetailOut, PaperOut, PaperUpdate,
    QuestionBankCreate, QuestionBankOut, QuestionBankUpdate, QuestionCreate,
    QuestionOut, QuestionUpdate, ReportStubOut, ResultDetailOut,
    ResultDetailResultOut, ResultOut, SubmitRequest, TodoItemOut,
)
from app.services.assessment_service import (
    STATUS_PENDING, AssessmentService,
)
from app.utils.pagination import paged_result
from app.utils.response import ok

router = APIRouter(dependencies=[Depends(require_permission("assessment:list"))])


# ============== 题库（A-1） ==============

@router.get("/banks", response_model=None)
def list_banks(keyword: str | None = None, status: int | None = Query(None, ge=0, le=1),
               page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
               db: Session = Depends(get_db)):
    total = QuestionBankDAO.count(db, keyword, status)
    rows = QuestionBankDAO.paged(db, keyword, status, page, page_size)
    items = []
    for b in rows:
        out = QuestionBankOut.model_validate(b)
        out.question_count = QuestionBankDAO.with_question_count(db, b)
        items.append(out)
    return ok(paged_result(items, page, page_size, total))


@router.get("/banks/{bank_id}", response_model=None)
def get_bank(bank_id: int, db: Session = Depends(get_db)):
    b = QuestionBankDAO.get(db, bank_id)
    if not b:
        raise HTTPException(404, "题库不存在")
    out = QuestionBankOut.model_validate(b)
    out.question_count = QuestionBankDAO.with_question_count(db, b)
    return ok(out)


@router.post("/banks", response_model=None,
             dependencies=[Depends(require_permission("assessment:bank"))])
def create_bank(body: QuestionBankCreate, db: Session = Depends(get_db)):
    b = AssessmentService.create_bank(db, body)
    db.commit()
    out = QuestionBankOut.model_validate(b)
    out.question_count = 0
    return ok(out)


@router.put("/banks/{bank_id}", response_model=None,
            dependencies=[Depends(require_permission("assessment:bank"))])
def update_bank(bank_id: int, body: QuestionBankUpdate, db: Session = Depends(get_db)):
    b = QuestionBankDAO.get(db, bank_id)
    if not b:
        raise HTTPException(404, "题库不存在")
    b = AssessmentService.update_bank(db, b, body)
    db.commit()
    out = QuestionBankOut.model_validate(b)
    out.question_count = QuestionBankDAO.with_question_count(db, b)
    return ok(out)


@router.delete("/banks/{bank_id}", response_model=None,
               dependencies=[Depends(require_permission("assessment:bank"))])
def delete_bank(bank_id: int, db: Session = Depends(get_db)):
    b = QuestionBankDAO.get(db, bank_id)
    if not b:
        raise HTTPException(404, "题库不存在")
    AssessmentService.delete_bank(db, b)
    db.commit()
    return ok()


# ============== 题目（A-1） ==============

@router.get("/banks/{bank_id}/questions", response_model=None)
def list_questions(bank_id: int, type: str | None = None, dimension: str | None = None,
                   difficulty: int | None = Query(None, ge=1, le=5),
                   keyword: str | None = None,
                   page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                   db: Session = Depends(get_db)):
    # bank_id=0 表示查全部题库（供题目管理页跨题库浏览）
    real_bank_id = None if bank_id == 0 else bank_id
    total = QuestionDAO.count(db, bank_id=real_bank_id, type_=type, dimension=dimension,
                              difficulty=difficulty, keyword=keyword)
    rows = QuestionDAO.paged(db, bank_id=real_bank_id, type_=type, dimension=dimension,
                             difficulty=difficulty, keyword=keyword, page=page, page_size=page_size)
    return ok(paged_result([QuestionOut.from_model(q) for q in rows], page, page_size, total))


@router.post("/questions", response_model=None,
             dependencies=[Depends(require_permission("assessment:question"))])
def create_question(body: QuestionCreate, db: Session = Depends(get_db)):
    q = AssessmentService.create_question(db, body)
    db.commit()
    return ok(QuestionOut.from_model(q))


@router.put("/questions/{question_id}", response_model=None,
            dependencies=[Depends(require_permission("assessment:question"))])
def update_question(question_id: int, body: QuestionUpdate, db: Session = Depends(get_db)):
    q = QuestionDAO.get(db, question_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    q = AssessmentService.update_question(db, q, body)
    db.commit()
    return ok(QuestionOut.from_model(q))


@router.delete("/questions/{question_id}", response_model=None,
               dependencies=[Depends(require_permission("assessment:question"))])
def delete_question(question_id: int, db: Session = Depends(get_db)):
    q = QuestionDAO.get(db, question_id)
    if not q:
        raise HTTPException(404, "题目不存在")
    # 已被试卷引用不允许删
    from app.models.assessment import PaperQuestion
    used = db.scalar(select(PaperQuestion).where(
        PaperQuestion.question_id == question_id).limit(1))
    if used:
        raise HTTPException(400, "该题目已被试卷引用，不能删除")
    QuestionDAO.delete(db, q)
    db.commit()
    return ok()


# ============== 试卷（A-2） ==============

@router.get("/papers", response_model=None)
def list_papers(keyword: str | None = None, status: int | None = Query(None, ge=0, le=1),
                page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                db: Session = Depends(get_db)):
    total = PaperDAO.count(db, keyword, status)
    rows = PaperDAO.paged(db, keyword, status, page, page_size)
    items = []
    for p in rows:
        out = PaperOut.model_validate(p)
        out.question_count = len(p.items)
        items.append(out)
    return ok(paged_result(items, page, page_size, total))


@router.get("/papers/{paper_id}", response_model=None)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    p = PaperDAO.get(db, paper_id)
    if not p:
        raise HTTPException(404, "试卷不存在")
    out = PaperDetailOut.model_validate(p)
    out.question_count = len(p.items)
    out.questions = [QuestionOut.from_model(pq.question) for pq in p.items]
    return ok(out)


@router.post("/papers", response_model=None,
             dependencies=[Depends(require_permission("assessment:paper"))])
def create_paper(body: PaperCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    p = AssessmentService.create_paper(db, body, user.id)
    db.commit()
    out = PaperDetailOut.model_validate(p)
    out.question_count = len(p.items)
    out.questions = [QuestionOut.from_model(pq.question) for pq in p.items]
    return ok(out)


@router.post("/papers/auto", response_model=None,
             dependencies=[Depends(require_permission("assessment:paper"))])
def create_paper_auto(body: PaperAutoCreate, user=Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """智能抽题组卷：AI 按条件从题库自动选题。"""
    p = AssessmentService.create_paper_auto(db, body, user.id)
    db.commit()
    out = PaperDetailOut.model_validate(p)
    out.question_count = len(p.items)
    out.questions = [QuestionOut.from_model(pq.question) for pq in p.items]
    return ok(out)


@router.put("/papers/{paper_id}", response_model=None,
            dependencies=[Depends(require_permission("assessment:paper"))])
def update_paper(paper_id: int, body: PaperUpdate, db: Session = Depends(get_db)):
    p = PaperDAO.get(db, paper_id)
    if not p:
        raise HTTPException(404, "试卷不存在")
    p = AssessmentService.update_paper(db, p, body)
    db.commit()
    out = PaperDetailOut.model_validate(p)
    out.question_count = len(p.items)
    out.questions = [QuestionOut.from_model(pq.question) for pq in p.items]
    return ok(out)


@router.delete("/papers/{paper_id}", response_model=None,
               dependencies=[Depends(require_permission("assessment:paper"))])
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    p = PaperDAO.get(db, paper_id)
    if not p:
        raise HTTPException(404, "试卷不存在")
    AssessmentService.delete_paper(db, p)
    db.commit()
    return ok()


# ============== 发起（A-3） ==============

@router.post("/launch", response_model=None,
             dependencies=[Depends(require_permission("assessment:launch"))])
def launch(body: LaunchRequest, db: Session = Depends(get_db)):
    items = AssessmentService.launch(db, body.paper_id, body.talent_ids)
    # 关联人才姓名（用于返回）
    talents = {t.id: t.name for t in db.query(Talent).filter(
        Talent.id.in_([i.talent_id for i in items])).all()}
    out_items = [LaunchResultItem(
        result_id=i.id, talent_id=i.talent_id, talent_name=talents.get(i.talent_id),
        paper_id=i.paper_id, status=i.status,
    ) for i in items]
    db.commit()
    return ok(LaunchResponse(
        paper_id=body.paper_id,
        launched_count=len(items),
        items=out_items,
    ))


# ============== 待测 / 答题视图 / 提交（A-4） ==============

@router.get("/todo", response_model=None)
def todo(talent_id: int = Query(..., description="人才 ID"),
         db: Session = Depends(get_db)):
    rows = ResultDAO.todo_by_talent(db, talent_id)
    items = []
    for r in rows:
        items.append(TodoItemOut(
            result_id=r.id, paper_id=r.paper_id, paper_title=r.paper.title,
            duration=r.paper.duration, total_score=r.paper.total_score,
            status=r.status, question_count=len(r.paper.items), created_at=r.created_at,
        ))
    return ok(items)


@router.get("/results/{result_id}/answer", response_model=None)
def get_answer_view(result_id: int, db: Session = Depends(get_db)):
    r = ResultDAO.get(db, result_id)
    if not r:
        raise HTTPException(404, "测评批次不存在")
    if r.status in (2, 3):
        raise HTTPException(400, "该批次已结束")
    # 进入答题状态
    AssessmentService.start(db, r)
    db.commit()
    items = []
    for pq in r.paper.items:
        q = pq.question
        opts = None
        if q.options:
            try:
                import json
                opts = json.loads(q.options)
            except Exception:
                opts = None
        items.append(AnswerViewQuestion(
            id=q.id, type=q.type, content=q.content, options=opts,
            score=q.score, dimension=q.dimension, sort=pq.sort,
        ))
    previous = []
    if r.answer_json:
        try:
            import json
            arr = json.loads(r.answer_json)
            previous = [AnswerItem(question_id=a["question_id"], user_answer=a["user_answer"])
                        for a in arr]
        except Exception:
            pass
    return ok(AnswerViewOut(
        result_id=r.id, paper_id=r.paper_id, paper_title=r.paper.title,
        duration=r.paper.duration, total_score=r.paper.total_score,
        status=r.status, questions=items, previous_answers=previous,
    ))


@router.post("/results/{result_id}/submit", response_model=None)
def submit(result_id: int, body: SubmitRequest, db: Session = Depends(get_db)):
    r = ResultDAO.get(db, result_id)
    if not r:
        raise HTTPException(404, "测评批次不存在")
    r = AssessmentService.submit(db, r, body.answers)
    db.commit()
    return ok(ResultDetailResultOut.model_validate({
        **ResultOut.model_validate(r).model_dump(),
        "details": [ResultDetailOut.from_model(d) for d in r.details],
    }))


# ============== 成绩（A-5） ==============

@router.get("/stats", response_model=None)
def assessment_stats(db: Session = Depends(get_db)):
    """测评域统计（供测评首页看板）：总数/已完成/平均分/合格率/状态分布。"""
    rows = db.query(Result).all()
    total = len(rows)
    submitted = sum(1 for r in rows if r.status >= 2)
    reported = sum(1 for r in rows if r.status == 3)
    # 平均分（按已交卷的）
    scored = [r.score for r in rows if r.status >= 2 and r.total_count]
    avg_score = round(sum(scored) / len(scored), 1) if scored else 0
    # 合格率：得分 / 卷面实际总分 >= 60% 视为合格
    passed = 0
    graded = 0
    for r in rows:
        if r.status >= 2:
            paper_total = sum((d.question.score for d in r.details), 0) or 1
            graded += 1
            if r.score / paper_total >= 0.6:
                passed += 1
    pass_rate = round(passed / graded * 100, 1) if graded else 0
    # 状态分布
    status_map = {0: "未作答", 1: "答题中", 2: "已交卷", 3: "已出报告"}
    by_status = {v: 0 for v in status_map.values()}
    for r in rows:
        by_status[status_map.get(r.status, "未知")] += 1
    return ok({
        "total": total,
        "submitted": submitted,
        "reported": reported,
        "avg_score": avg_score,
        "pass_rate": pass_rate,
        "by_status": by_status,
        "recent": [ResultOut.model_validate(r) for r in sorted(rows, key=lambda x: x.id, reverse=True)[:8]],
    })


@router.get("/results", response_model=None)
def list_results(paper_id: int | None = None, status: int | None = Query(None, ge=0, le=3),
                 talent_id: int | None = None,
                 page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=200),
                 db: Session = Depends(get_db)):
    total = ResultDAO.count(db, paper_id, status, talent_id)
    rows = ResultDAO.paged(db, paper_id, status, talent_id, page, page_size)
    return ok(paged_result([ResultOut.model_validate(r) for r in rows], page, page_size, total))


@router.get("/results/{result_id}", response_model=None)
def get_result(result_id: int, db: Session = Depends(get_db)):
    r = ResultDAO.get(db, result_id)
    if not r:
        raise HTTPException(404, "测评批次不存在")
    return ok(ResultDetailResultOut.model_validate({
        **ResultOut.model_validate(r).model_dump(),
        "details": [ResultDetailOut.from_model(d) for d in r.details],
    }))


# ============== Agent② 报告（A-6） ==============

@router.get("/results/{result_id}/report", response_model=None)
def get_report(result_id: int, db: Session = Depends(get_db)):
    r = ResultDAO.get(db, result_id)
    if not r:
        raise HTTPException(404, "测评批次不存在")
    if r.status in (STATUS_PENDING,) or r.report_json is None:
        report = AssessmentService.generate_report(db, r)
    else:
        import json
        report = json.loads(r.report_json)
    db.commit()
    return ok(ReportStubOut(result_id=r.id, **report))


# 内部引用，避免 linter 报 unused
_ = (ResultDetail, datetime)
