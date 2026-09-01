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
from app.models.training import Course, ExamResult, LearningRecord, TrainingPlan
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
               course_ids: list[int], deadline, generated_by: str = "manual") -> TrainingPlan:
        plan = PlanDAO.create(
            db, talent_id=talent_id, title=title,
            course_ids=",".join(map(str, course_ids)) if course_ids else "",
            source="manual" if generated_by == "manual" else "agent",
            deadline=deadline, generated_by=generated_by,
        )
        return plan

    @staticmethod
    def update_progress(db: Session, *, plan_id: int, talent_id: int,
                        course_id: int, lesson_id: int, progress: int) -> LearningRecord:
        rec = RecordDAO.get_by(db, plan_id=plan_id, talent_id=talent_id, course_id=course_id)
        if rec:
            return RecordDAO.update(db, rec, lesson_id=lesson_id, progress=progress)
        return RecordDAO.create(
            db, plan_id=plan_id, talent_id=talent_id, course_id=course_id,
            lesson_id=lesson_id, progress=progress,
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
