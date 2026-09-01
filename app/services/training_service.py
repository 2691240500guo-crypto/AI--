"""智能培训域 TR 业务服务（TR-1 ~ TR-5）。

跨模块依赖标注：
- MessageService：来自消息域（同事负责），本模块仅「调用」，不改其代码。
- LLM（Agent④）：见 training_agent.py，此处不引入，保持 service 可无 AI 运行。
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.training import (CourseDAO, ExamDAO, ExamResultDAO, LessonDAO,
                              PlanDAO, RecordDAO)
from app.models.talent import Talent
from app.models.training import (Course, Exam, ExamResult, LearningRecord,
                                  TrainingPlan)
from app.utils.response import BusinessError


class TrainingService:
    # ---------- 课程 / 课节（E01）----------
    @staticmethod
    def list_lessons(db: Session, course_id: int) -> list:
        return LessonDAO.list(db, LessonDAO.__model__.course_id == course_id,
                              order_by=LessonDAO.__model__.sort)


# ---------- 学习计划（E02）----------
class PlanService:
    @staticmethod
    def create(db: Session, *, talent_id: int, title: str,
               course_ids: list[int], deadline, generated_by: str = "manual",
               weakness_tags: list[str] | None = None) -> TrainingPlan:
        plan = PlanDAO.create(
            db, talent_id=talent_id, title=title,
            course_ids=",".join(map(str, course_ids)) if course_ids else "",
            source="manual" if generated_by == "manual" else "agent",
            deadline=deadline, generated_by=generated_by,
            weakness_tags=",".join(weakness_tags) if weakness_tags else "",
        )
        return plan

    @staticmethod
    def update_progress(db: Session, *, plan_id: int, talent_id: int,
                        course_id: int, lesson_id: int, progress: int,
                        learned_minutes: int = 0) -> LearningRecord:
        rec = RecordDAO.get_by(db, plan_id=plan_id, talent_id=talent_id, course_id=course_id)
        if rec:
            return RecordDAO.update(db, rec, lesson_id=lesson_id, progress=progress,
                                    learned_minutes=learned_minutes)
        return RecordDAO.create(
            db, plan_id=plan_id, talent_id=talent_id, course_id=course_id,
            lesson_id=lesson_id, progress=progress, learned_minutes=learned_minutes,
        )


# ---------- 在线考核 / 成绩（E03）----------
class ExamService:
    @staticmethod
    def submit(db: Session, *, exam_id: int, talent_id: int, answers: dict[int, str]) -> ExamResult:
        """交卷自动阅卷。

        判分口径（MVP，无标准答案时的兜底规则）：
        - question_ids / answers 直接对答案做「完全匹配」判分；
        - 因题目标准答案在测评域 asm_question（同事 A 域），此处留接口：
          get_correct_answer(question_id) 由同事提供或后续接入；
        - 当前兜底：score 按「答对题目数 / 总题数 * 100」估算，is_pass 按 pass_score 判定。
        """
        exam = ExamDAO.get(db, exam_id)
        if not exam:
            raise BusinessError(404, "考核不存在")
        q_ids = [int(x) for x in exam.question_ids.split(",") if x]
        # TODO: 接入测评域标准答案后，替换为逐题判分
        correct = 0
        for qid in q_ids:
            if answers.get(qid) is not None:  # 有作答即暂视为正确，后续接标准答案
                correct += 1
        total = len(q_ids) or 1
        score = int(correct / total * 100)
        result = ExamResultDAO.create(
            db, exam_id=exam_id, talent_id=talent_id, score=score,
            is_pass=1 if score >= exam.pass_score else 0,
            answer_json=str(answers),
        )
        return result


# ---------- 效果分析（E05）----------
class EffectService:
    @staticmethod
    def overview(db: Session) -> dict:
        """TR-5 效果分析聚合，供数据决策域 D 看板消费。"""
        total_courses = db.scalar(select(func.count()).select_from(Course)) or 0
        total_plans = db.scalar(select(func.count()).select_from(TrainingPlan)) or 0
        total_records = db.scalar(select(func.count()).select_from(LearningRecord)) or 0
        avg_progress = db.scalar(select(func.avg(LearningRecord.progress))) or 0
        total_exams = db.scalar(select(func.count()).select_from(ExamResult)) or 0
        passed = db.scalar(
            select(func.count()).select_from(ExamResult).where(ExamResult.is_pass == 1)) or 0
        pass_rate = round(passed / total_exams * 100, 2) if total_exams else 0
        return {
            "total_courses": total_courses,
            "total_plans": total_plans,
            "total_records": total_records,
            "avg_progress": round(float(avg_progress), 2),
            "total_exams": total_exams,
            "pass_rate": pass_rate,
        }

    # 计划状态 int -> 前端字符串枚举（前端 planStatusMap 的 key）
    PLAN_STATUS_KEYS = {0: "not_started", 1: "in_progress", 2: "done", 3: "overdue"}
    PLAN_STATUS_CN = {"not_started": "未开始", "in_progress": "进行中",
                      "done": "已完成", "overdue": "已逾期"}

    @staticmethod
    def overview_full(db: Session) -> dict:
        """效果分析全量版（培训管理端 effect 页专用）。
        数据量为班级项目规模，直接全量载入内存聚合，避免复杂 SQL。"""
        courses = list(db.scalars(select(Course)).all())
        plans = list(db.scalars(select(TrainingPlan)).all())
        records = list(db.scalars(select(LearningRecord)).all())
        exams = list(db.scalars(select(Exam)).all())
        results = list(db.scalars(select(ExamResult)).all())

        course_map = {c.id: c for c in courses}
        exam_plan = {e.id: e.plan_id for e in exams}
        rec_by_plan: dict[int, list] = {}
        for r in records:
            rec_by_plan.setdefault(r.plan_id, []).append(r)

        def plan_progress(p: TrainingPlan) -> int:
            recs = rec_by_plan.get(p.id, [])
            return round(sum(x.progress for x in recs) / len(recs)) if recs else 0

        def plan_hours(p: TrainingPlan) -> float:
            return sum((course_map[r.course_id].score if r.course_id in course_map else 0)
                       * r.progress / 100 for r in rec_by_plan.get(p.id, []))

        # ---- 汇总 KPI ----
        learned_hours = sum(plan_hours(p) for p in plans)
        done_plans = [p for p in plans if p.status == 2]
        passed = [r for r in results if r.is_pass == 1]
        summary = {
            "course_count": len(courses),
            "plan_count": len(plans),
            "learned_hours": round(learned_hours, 1),
            "completed_rate": round(len(done_plans) / len(plans) * 100) if plans else 0,
            "pass_rate": round(len(passed) / len(results) * 100) if results else 0,
            "avg_progress": round(sum(plan_progress(p) for p in plans) / len(plans)) if plans else 0,
            "avg_improvement": round(sum((p.improvement or 0) for p in plans) / len(plans)) if plans else 0,
        }

        # ---- 分类学时分布 ----
        cat_hours: dict[str, float] = {}
        for r in records:
            c = course_map.get(r.course_id)
            if not c:
                continue
            cat_hours[c.category] = cat_hours.get(c.category, 0) + (c.score or 0) * r.progress / 100
        category_hours = [{"name": k, "hours": round(v, 1)} for k, v in cat_hours.items()]

        # ---- 计划状态分布（前端字符串枚举 key）----
        counts = {k: 0 for k in EffectService.PLAN_STATUS_CN}
        for p in plans:
            key = EffectService.PLAN_STATUS_KEYS.get(p.status, "not_started")
            counts[key] = counts.get(key, 0) + 1
        status_data = [{"status": k, "name": cn, "count": counts.get(k, 0)}
                       for k, cn in EffectService.PLAN_STATUS_CN.items()]

        # ---- 月度趋势（按学习记录/成绩/计划的月份聚合，不建趋势表）----
        months: dict[str, dict] = {}

        def bucket(mkey: str):
            return months.setdefault(mkey, {"hours": 0.0, "exams": 0, "passed": 0,
                                            "imp_sum": 0, "imp_n": 0})

        for r in records:
            b = bucket((r.updated_at or datetime.now()).strftime("%Y-%m"))
            c = course_map.get(r.course_id)
            b["hours"] += (c.score if c else 0) * r.progress / 100
        for res in results:
            b = bucket((res.created_at or datetime.now()).strftime("%Y-%m"))
            b["exams"] += 1
            if res.is_pass == 1:
                b["passed"] += 1
        for p in plans:
            b = bucket((p.created_at or datetime.now()).strftime("%Y-%m"))
            b["imp_sum"] += p.improvement or 0
            b["imp_n"] += 1
        trends = []
        for mkey in sorted(months):
            b = months[mkey]
            trends.append({
                "month": f"{int(mkey.split('-')[1])}月",
                "hours": round(b["hours"], 1),
                "pass_rate": round(b["passed"] / b["exams"] * 100) if b["exams"] else 0,
                "improvement": round(b["imp_sum"] / b["imp_n"]) if b["imp_n"] else 0,
            })

        # ---- 课程效果排行 ----
        ranking = []
        for c in courses:
            crecs = [r for r in records if r.course_id == c.id]
            hours = sum((c.score or 0) * r.progress / 100 for r in crecs)
            pids = [p.id for p in plans
                    if str(c.id) in [x for x in (p.course_ids or "").split(",") if x]]
            eids = [e.id for e in exams if e.plan_id in pids]
            eres = [r for r in results if r.exam_id in eids]
            pr = round(sum(1 for r in eres if r.is_pass == 1) / len(eres) * 100) if eres else 0
            ranking.append({"id": c.id, "title": c.title, "category": c.category,
                            "learner_count": len(crecs),
                            "learned_hours": round(hours, 1), "pass_rate": pr})
        ranking.sort(key=lambda x: -x["learned_hours"])

        # ---- 人员培训效果明细 ----
        talent_names = {}
        tids = {p.talent_id for p in plans}
        if tids:
            talent_names = {t.id: t.name for t in db.scalars(
                select(Talent).where(Talent.id.in_(tids))).all()}
        talent_effects = []
        for p in plans:
            eres = [r for r in results if exam_plan.get(r.exam_id) == p.id]
            key = EffectService.PLAN_STATUS_KEYS.get(p.status, "not_started")
            talent_effects.append({
                "id": p.id,
                "title": p.title,
                "talent_name": talent_names.get(p.talent_id, f"人才#{p.talent_id}"),
                "progress": plan_progress(p),
                "learned_hours": round(plan_hours(p), 1),
                "exam_avg": round(sum(r.score for r in eres) / len(eres)) if eres else None,
                "improvement": p.improvement or 0,
                "status_label": EffectService.PLAN_STATUS_CN.get(key, "-"),
            })

        return {
            "summary": summary,
            "category_hours": category_hours,
            "status_data": status_data,
            "trends": trends,
            "ranking": ranking,
            "talent_effects": talent_effects,
        }
