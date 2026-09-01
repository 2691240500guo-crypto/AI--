"""智能测评域业务：题库/题目/试卷/发起/作答/判分/报告 stub。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dao.assessment import (
    PaperDAO, QuestionBankDAO, QuestionDAO, ResultDAO,
)
from app.models.assessment import (
    Paper, PaperQuestion, Question, QuestionBank, Result, ResultDetail,
)
from app.utils.response import BusinessError


# 状态机常量
STATUS_PENDING = 0   # 未作答（已发起未开始）
STATUS_DOING = 1     # 答题中
STATUS_SUBMITTED = 2  # 已交卷
STATUS_REPORTED = 3   # 已出报告


class AssessmentService:
    """业务逻辑：组装题库/题目/试卷/批次。"""

    # ----------------- 题库 -----------------

    @staticmethod
    def create_bank(db: Session, data) -> QuestionBank:
        if QuestionBankDAO.get_by(db, name=data.name):
            raise BusinessError(400, "题库名已存在")
        return QuestionBankDAO.create(db, name=data.name,
                                      description=data.description, status=data.status)

    @staticmethod
    def update_bank(db: Session, bank: QuestionBank, data) -> QuestionBank:
        if data.name and data.name != bank.name:
            if QuestionBankDAO.get_by(db, name=data.name):
                raise BusinessError(400, "题库名已存在")
        return QuestionBankDAO.update(db, bank, **{k: v for k, v in data.model_dump(exclude_unset=True).items()})

    @staticmethod
    def delete_bank(db: Session, bank: QuestionBank) -> None:
        # 已被试卷引用的题目不允许删除题库（避免悬空）
        from app.models.assessment import PaperQuestion
        used = db.scalar(select(PaperQuestion).where(
            PaperQuestion.question_id.in_(
                select(Question.id).where(Question.bank_id == bank.id)
            )
        ).limit(1))
        if used:
            raise BusinessError(400, "该题库已被试卷引用，不能删除")
        QuestionBankDAO.delete(db, bank)

    # ----------------- 题目 -----------------

    @staticmethod
    def _serialize_options(options) -> str | None:
        if not options:
            return None
        return json.dumps([o.model_dump() if hasattr(o, "model_dump") else o for o in options],
                          ensure_ascii=False)

    @staticmethod
    def create_question(db: Session, data) -> Question:
        bank = QuestionBankDAO.get(db, data.bank_id)
        if not bank:
            raise BusinessError(404, "题库不存在")
        if data.type != "judge" and (not data.options or len(data.options) < 2):
            raise BusinessError(400, "单选/多选题至少 2 个选项")
        return QuestionDAO.create(
            db, bank_id=data.bank_id, type=data.type, content=data.content,
            options=AssessmentService._serialize_options(data.options),
            answer=data.answer, dimension=data.dimension, difficulty=data.difficulty,
            score=data.score, status=data.status,
        )

    @staticmethod
    def update_question(db: Session, q: Question, data) -> Question:
        fields = data.model_dump(exclude_unset=True)
        if "options" in fields:
            fields["options"] = AssessmentService._serialize_options(fields["options"])
        return QuestionDAO.update(db, q, **fields)

    # ----------------- 试卷 -----------------

    @staticmethod
    def _replace_paper_questions_db(db: Session, paper: Paper, question_ids: list[int]) -> int:
        paper.items.clear()
        if not question_ids:
            return 0
        questions = list(db.scalars(select(Question).where(Question.id.in_(question_ids))))
        valid = {q.id: q for q in questions if q.status == 1}
        if len(valid) != len(set(question_ids)):
            raise BusinessError(400, "部分题目不存在或已停用")
        total = 0
        for sort, qid in enumerate(question_ids):
            q = valid[qid]
            paper.items.append(PaperQuestion(question_id=qid, sort=sort))
            total += q.score
        return total

    @staticmethod
    def create_paper(db: Session, data, user_id: int | None) -> Paper:
        paper = Paper(title=data.title, description=data.description,
                      difficulty=data.difficulty, duration=data.duration,
                      generation_mode=getattr(data, "generation_mode", "manual"),
                      total_score=0, status=data.status)
        db.add(paper)
        db.flush()
        total = AssessmentService._replace_paper_questions_db(db, paper, data.question_ids)
        paper.total_score = total
        db.flush()
        return paper

    @staticmethod
    def create_paper_auto(db: Session, data, user_id: int | None) -> Paper:
        """智能抽题组卷：按维度/难度/题数条件从题库自动选题（维度均衡优先）。"""
        from sqlalchemy import func
        from app.models.assessment import Question
        q = db.query(Question).filter(Question.status == 1)
        if data.dimension:
            q = q.filter(Question.dimension == data.dimension)
        if data.difficulty:
            q = q.filter(Question.difficulty == data.difficulty)
        pool = q.all()
        if not pool:
            raise BusinessError(400, "符合条件（维度/难度）的题目不足，请调整条件")
        import random
        random.shuffle(pool)
        picked = pool[:data.question_count]
        # 维度均衡：如果指定了维度但题不够，从全库补
        if len(picked) < data.question_count:
            rest = db.query(Question).filter(Question.status == 1,
                                             Question.id.notin_([x.id for x in picked])).all()
            random.shuffle(rest)
            picked += rest[: data.question_count - len(picked)]

        paper = Paper(title=data.title, description=data.description,
                      difficulty=data.difficulty or 1, duration=data.duration,
                      generation_mode="auto", total_score=0, status=data.status, created_by=user_id)
        db.add(paper)
        db.flush()
        for i, question in enumerate(picked):
            db.add(PaperQuestion(paper_id=paper.id, question_id=question.id, sort=i))
        paper.total_score = sum(q.score for q in picked)
        db.flush()
        return paper

    @staticmethod
    def update_paper(db: Session, paper: Paper, data) -> Paper:
        fields = data.model_dump(exclude_unset=True)
        if "question_ids" in fields:
            total = AssessmentService._replace_paper_questions_db(db, paper, fields.pop("question_ids"))
            paper.total_score = total
        for k, v in fields.items():
            setattr(paper, k, v)
        db.flush()
        return paper

    @staticmethod
    def delete_paper(db: Session, paper: Paper) -> None:
        # 有进行中的批次不允许删
        busy = db.scalar(select(Result).where(
            Result.paper_id == paper.id, Result.status.in_([STATUS_PENDING, STATUS_DOING])
        ).limit(1))
        if busy:
            raise BusinessError(400, "该试卷存在未完成的批次，不能删除")
        PaperDAO.delete(db, paper)

    # ----------------- 发起 -----------------

    @staticmethod
    def launch(db: Session, paper_id: int, talent_ids: list[int]) -> list[Result]:
        paper = PaperDAO.get(db, paper_id)
        if not paper:
            raise BusinessError(404, "试卷不存在")
        if paper.status != 1:
            raise BusinessError(400, "试卷已停用")
        if not paper.items:
            raise BusinessError(400, "试卷没有题目，不能发起")
        # 去重 + 过滤已存在未完成的批次
        existing = set(db.scalars(select(Result.talent_id).where(
            Result.paper_id == paper_id,
            Result.talent_id.in_(talent_ids),
            Result.status.in_([STATUS_PENDING, STATUS_DOING]),
        )).all())
        new_ids = [tid for tid in dict.fromkeys(talent_ids) if tid not in existing]
        # 校验人才存在
        from app.models.talent import Talent
        valid_talents = set(db.scalars(select(Talent.id).where(
            Talent.id.in_(new_ids))).all())
        invalid = [tid for tid in new_ids if tid not in valid_talents]
        if invalid:
            raise BusinessError(400, f"人才不存在：{invalid[:5]}{'...' if len(invalid) > 5 else ''}")
        results: list[Result] = []
        for tid in new_ids:
            r = Result(talent_id=tid, paper_id=paper_id, status=STATUS_PENDING)
            db.add(r)
            results.append(r)
        db.flush()
        return results

    # ----------------- 作答 / 判分 -----------------

    @staticmethod
    def _normalize_answer(type_: str, raw: str) -> str:
        raw = (raw or "").strip()
        if type_ == "multi":
            parts = sorted({p.strip().upper() for p in raw.split(",") if p.strip()})
            return ",".join(parts)
        if type_ == "judge":
            return raw.lower() if raw.lower() in {"true", "false"} else ""
        return raw.upper()

    @staticmethod
    def _is_correct(question: Question, user_answer: str) -> bool:
        if question.type == "judge":
            return user_answer == question.answer.lower()
        if question.type == "multi":
            return set(user_answer.split(",")) == set(question.answer.split(","))
        return user_answer == question.answer

    @staticmethod
    def start(db: Session, result: Result) -> Result:
        if result.status == STATUS_SUBMITTED or result.status == STATUS_REPORTED:
            raise BusinessError(400, "该批次已结束")
        if result.status == STATUS_PENDING:
            result.status = STATUS_DOING
            result.started_at = datetime.now()
            db.flush()
        return result

    @staticmethod
    def submit(db: Session, result: Result, answers: list) -> Result:
        if result.status == STATUS_SUBMITTED or result.status == STATUS_REPORTED:
            raise BusinessError(400, "该批次已交卷")
        if result.status == STATUS_PENDING:
            result.started_at = result.started_at or datetime.now()
        result.end_at = datetime.now()

        # 加载试卷题目（用排序后的 items）
        questions = {pq.question_id: pq.question for pq in result.paper.items}

        # 答案按 question_id 索引
        answer_map: dict[int, str] = {}
        for a in answers:
            qid = int(a.question_id)
            user_raw = a.user_answer if isinstance(a, dict) else a.user_answer
            q = questions.get(qid)
            if not q:
                continue
            user_norm = AssessmentService._normalize_answer(q.type, user_raw)
            answer_map[qid] = user_norm

        # 清理旧 detail（如部分保存过）
        for d in list(result.details):
            db.delete(d)
        db.flush()

        score = 0
        correct = 0
        for qid, q in questions.items():
            user_ans = answer_map.get(qid, "")
            ok = AssessmentService._is_correct(q, user_ans)
            gained = q.score if ok else 0
            if ok:
                correct += 1
            score += gained
            result.details.append(ResultDetail(
                question_id=qid, user_answer=user_ans or None, is_correct=1 if ok else 0, score=gained,
            ))
        result.score = score
        result.correct_count = correct
        result.answer_json = json.dumps(
            [{"question_id": qid, "user_answer": ans} for qid, ans in answer_map.items()],
            ensure_ascii=False,
        )
        result.status = STATUS_SUBMITTED
        db.flush()
        return result

    # ----------------- Agent② 报告（stub） -----------------

    LEVEL_THRESHOLD = [(90, "S"), (75, "A"), (60, "B"), (0, "C")]

    @classmethod
    def _level_for(cls, score: int, total: int) -> str:
        if total <= 0:
            return "C"
        ratio = score / total * 100
        for th, lv in cls.LEVEL_THRESHOLD:
            if ratio >= th:
                return lv
        return "C"

    @classmethod
    def generate_report(cls, db: Session, result: Result) -> dict:
        """Agent② 测评报告：规则算雷达/评级（保证结构稳定）+ LLM 生成综合评价。

        LLM 不可用或超时自动降级为规则总结，不影响出报告。
        """
        if result.status not in (STATUS_SUBMITTED, STATUS_REPORTED):
            raise BusinessError(400, "请先交卷再生成报告")

        # 维度聚合（规则，保证准确）
        dim_total: dict[str, int] = {}
        dim_score: dict[str, int] = {}
        for d in result.details:
            q = d.question
            dim = q.dimension or "通用"
            dim_total[dim] = dim_total.get(dim, 0) + q.score
            dim_score[dim] = dim_score.get(dim, 0) + d.score
        radar = {dim: round(dim_score[dim] / dim_total[dim] * 100, 1) if dim_total[dim] else 0
                 for dim in dim_total}

        # 优势（>=75）/ 短板（<60），规则提取
        strengths = [d for d, v in radar.items() if v >= 75]
        weaknesses = [d for d, v in radar.items() if v < 60]

        actual_total = sum((d.question.score for d in result.details), 0) or 1
        level = cls._level_for(result.score, actual_total)

        # 人才姓名（供 LLM prompt）
        talent_name = None
        try:
            from app.models.talent import Talent
            t = db.get(Talent, result.talent_id)
            talent_name = t.name if t else None
        except Exception:
            talent_name = None

        # LLM 生成综合评价（失败降级为规则总结）
        summary = cls._llm_summary(
            talent_name, result.score, actual_total, result.correct_count,
            result.total_count, radar, strengths, weaknesses, level,
        )

        report = {
            "level": level,
            "radar": radar,
            "strengths": strengths or ["暂无明显优势"],
            "weaknesses": weaknesses or ["暂无明显短板"],
            "suggestions": [f"针对【{w}】维度进行专项训练与提升" for w in weaknesses]
                           or ["保持当前水平，继续拓展"],
            "summary": summary,
        }
        result.report_json = json.dumps(report, ensure_ascii=False)
        result.status = STATUS_REPORTED
        db.flush()
        return report

    @classmethod
    def _llm_summary(cls, talent_name: str | None, score: int, total: int,
                     correct: int, total_count: int, radar: dict,
                     strengths: list[str], weaknesses: list[str], level: str) -> str:
        """生成综合评价：优先 Dify 编排 → 回退直连 LLM → 回退规则总结。"""
        name = talent_name or "该人才"
        radar_str = "、".join(f"{k} {v}分" for k, v in radar.items())
        strengths_str = "、".join(strengths) if strengths else "无"
        weaknesses_str = "、".join(weaknesses) if weaknesses else "无"

        # 1) 优先 Dify workflow
        try:
            from app.utils.dify_client import get_dify
            dify = get_dify()
            if dify.available:
                outputs = dify.run_workflow({
                    "talent_name": name, "score": score, "total": total,
                    "correct": correct, "total_count": total_count,
                    "radar": radar_str, "strengths": strengths_str,
                    "weaknesses": weaknesses_str,
                })
                summary = (outputs.get("result") or {}).get("report_summary") or outputs.get("report_summary")
                if summary and len(str(summary)) >= 8:
                    return str(summary).strip()
        except Exception:
            pass

        # 2) 回退直连 LLM
        try:
            from app.utils.llm import get_llm
            prompt = (
                f"请为一位人才撰写测评综合评价（120 字以内，中文，直接给结论不加标题）。\n"
                f"人才：{name}\n"
                f"测评得分：{score}/{total}（正确 {correct}/{total_count} 题），综合评级 {level}。\n"
                f"各维度得分（0-100）：{radar_str}。\n"
                f"优势维度：{strengths_str}。\n"
                f"短板维度：{weaknesses_str}。\n"
                f"请结合短板给出 1-2 句发展建议。"
            )
            text = get_llm().chat(prompt, system="你是一位资深人才测评专家，输出简洁专业。",
                                  temperature=0.5)
            text = (text or "").strip()
            if len(text) < 8:
                raise ValueError("LLM 输出过短")
            return text
        except Exception:
            # 3) 降级：规则总结
            weak_txt = weaknesses_str if weaknesses else "无明显短板"
            return (f"本次测评得分 {score}/{total}，正确 {correct}/{total_count} 题，综合评级 {level}。"
                    f"优势维度：{strengths_str if strengths else '暂不明显'}；"
                    f"短板维度：{weak_txt}。建议针对短板进行专项训练提升。")
