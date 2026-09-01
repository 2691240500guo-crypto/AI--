"""C 智能测评 C01-C03 业务服务。"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import random
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dao.assessment import (
    AssessmentCapabilityModelDAO,
    AssessmentBatchDAO,
    AssessmentPaperDAO,
    AssessmentAnswerEventDAO,
    AssessmentQuestionDAO,
    AssessmentResultDAO,
    AssessmentResultDetailDAO,
    PaperQuestionDAO,
    QuestionBankDAO,
)
from app.dao.user import UserDAO
from app.models.assessment import (
    AssessmentCapabilityModel,
    AssessmentBatch,
    AssessmentPaper,
    AssessmentAnswerEvent,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentResultDetail,
    PaperQuestion,
    QuestionBank,
)
from app.models.dept import Position
from app.models.user import User
from app.schemas.assessment import (
    CapabilityModelCreate,
    CapabilityModelUpdate,
    LaunchRequest,
    PaperCreate,
    PaperUpdate,
    QuestionCreate,
    QuestionUpdate,
    RandomPaperRule,
)
from app.services.message_service import MessageService
from app.services.assessment_report_service import AssessmentReportService


class AssessmentService:
    """测评领域业务服务，保持 router -> service -> dao 单向依赖。"""

    @staticmethod
    def _validate_question_payload(question_type: str, options: list | None, answer: list | str | None) -> None:
        if answer is None or answer == [] or answer == "":
            raise ValueError("标准答案不能为空")
        if question_type in {"single", "multi"} and not options:
            raise ValueError("选择题必须提供选项")
        if question_type == "single" and isinstance(answer, list) and len(answer) != 1:
            raise ValueError("单选题只能有一个标准答案")
        if question_type == "multi" and not isinstance(answer, list):
            raise ValueError("多选题标准答案必须是数组")

    @staticmethod
    def _question_values(body: QuestionCreate | QuestionUpdate, existing: AssessmentQuestion | None = None) -> dict:
        values = body.model_dump(exclude_unset=True)
        question_type = values.get("type", existing.type if existing else None)
        options = values.get("options", existing.options if existing else None)
        answer = values.get("answer", existing.answer if existing else None)
        AssessmentService._validate_question_payload(question_type, options, answer)
        return values

    @staticmethod
    def list_banks(db: Session, *, keyword: str | None, status: int | None, page: int, page_size: int):
        return QuestionBankDAO.paged(db, keyword=keyword, status=status, page=page, page_size=page_size)

    @staticmethod
    def create_bank(db: Session, name: str, description: str) -> QuestionBank:
        if QuestionBankDAO.get_by(db, name=name):
            raise ValueError("题库名称已存在")
        return QuestionBankDAO.create(db, name=name, description=description, status=1)

    @staticmethod
    def update_bank(db: Session, bank_id: int, body: dict) -> QuestionBank:
        bank = QuestionBankDAO.get(db, bank_id)
        if not bank:
            raise LookupError("题库不存在")
        if body.get("name") and body["name"] != bank.name and QuestionBankDAO.get_by(db, name=body["name"]):
            raise ValueError("题库名称已存在")
        return QuestionBankDAO.update(db, bank, **body)

    @staticmethod
    def delete_bank(db: Session, bank_id: int) -> None:
        bank = QuestionBankDAO.get(db, bank_id)
        if not bank:
            raise LookupError("题库不存在")
        question_count = db.scalar(
            select(func.count()).select_from(AssessmentQuestion).where(AssessmentQuestion.bank_id == bank_id)
        ) or 0
        if question_count:
            raise ValueError("题库仍有题目，不能删除；请先停用或迁移题目")
        QuestionBankDAO.delete(db, bank)

    @staticmethod
    def list_questions(db: Session, **filters):
        return AssessmentQuestionDAO.paged(db, **filters)

    @staticmethod
    def list_bank_questions(db: Session, bank_id: int, *, active_only: bool = False) -> list[AssessmentQuestion]:
        if not QuestionBankDAO.get(db, bank_id):
            raise LookupError("题库不存在")
        return AssessmentQuestionDAO.list_by_bank(db, bank_id, active_only=active_only)

    @staticmethod
    def create_question(db: Session, body: QuestionCreate) -> AssessmentQuestion:
        if not QuestionBankDAO.get(db, body.bank_id):
            raise LookupError("题库不存在")
        values = AssessmentService._question_values(body)
        return AssessmentQuestionDAO.create(db, **values, status=1)

    @staticmethod
    def update_question(db: Session, question_id: int, body: QuestionUpdate) -> AssessmentQuestion:
        question = AssessmentQuestionDAO.get(db, question_id)
        if not question:
            raise LookupError("题目不存在")
        values = AssessmentService._question_values(body, question)
        if "bank_id" in values and not QuestionBankDAO.get(db, values["bank_id"]):
            raise LookupError("题库不存在")
        return AssessmentQuestionDAO.update(db, question, **values)

    @staticmethod
    def delete_question(db: Session, question_id: int) -> None:
        question = AssessmentQuestionDAO.get(db, question_id)
        if not question:
            raise LookupError("题目不存在")
        reference_count = db.scalar(
            select(func.count()).select_from(PaperQuestion).where(PaperQuestion.question_id == question_id)
        ) or 0
        if reference_count:
            raise ValueError("题目已被试卷引用，不能删除；请先停用题目")
        AssessmentQuestionDAO.delete(db, question)

    @staticmethod
    def list_positions(db: Session) -> list[Position]:
        return list(db.scalars(select(Position).order_by(Position.level.asc(), Position.id.asc())).all())

    @staticmethod
    def list_capability_models(db: Session, *, keyword: str | None, status: int | None,
                               page: int, page_size: int):
        return AssessmentCapabilityModelDAO.paged(
            db, keyword=keyword, status=status, page=page, page_size=page_size
        )

    @staticmethod
    def get_capability_model(db: Session, model_id: int) -> AssessmentCapabilityModel:
        model = AssessmentCapabilityModelDAO.get(db, model_id)
        if not model:
            raise LookupError("能力模型不存在")
        return model

    @staticmethod
    def _validate_capability_model(db: Session, body: CapabilityModelCreate | CapabilityModelUpdate,
                                   existing: AssessmentCapabilityModel | None = None) -> dict:
        values = body.model_dump(exclude_unset=True)
        name = values.get("name", existing.name if existing else None)
        duplicate = AssessmentCapabilityModelDAO.get_by(db, name=name) if name else None
        if duplicate and (not existing or duplicate.id != existing.id):
            raise ValueError("能力模型名称已存在")
        position_id = values.get("position_id", existing.position_id if existing else None)
        if position_id and not db.get(Position, position_id):
            raise LookupError("岗位不存在")
        rules = values.get("rules", existing.rules if existing else None)
        if not rules:
            raise ValueError("能力模型至少需要一条维度规则")
        normalized_rules = [rule.model_dump() if hasattr(rule, "model_dump") else dict(rule) for rule in rules]
        dimensions = [rule["dimension"].strip() for rule in normalized_rules]
        if len(dimensions) != len(set(dimensions)):
            raise ValueError("能力模型不能包含重复维度")
        for rule, dimension in zip(normalized_rules, dimensions):
            rule["dimension"] = dimension
            rule["bank_ids"] = sorted(set(rule.get("bank_ids") or []))
            rule["types"] = list(dict.fromkeys(rule.get("types") or []))
            rule["difficulties"] = sorted(set(rule.get("difficulties") or []))
            if any(value not in range(1, 6) for value in rule["difficulties"]):
                raise ValueError(f"维度“{dimension}”的难度必须在 1-5 之间")
            if rule["bank_ids"]:
                bank_count = db.scalar(select(func.count()).select_from(QuestionBank).where(
                    QuestionBank.id.in_(rule["bank_ids"])
                )) or 0
                if bank_count != len(rule["bank_ids"]):
                    raise LookupError(f"维度“{dimension}”包含不存在的题库")
        values["rules"] = normalized_rules
        return values

    @staticmethod
    def create_capability_model(db: Session, body: CapabilityModelCreate) -> AssessmentCapabilityModel:
        values = AssessmentService._validate_capability_model(db, body)
        return AssessmentCapabilityModelDAO.create(db, **values, status=1)

    @staticmethod
    def update_capability_model(db: Session, model_id: int,
                                body: CapabilityModelUpdate) -> AssessmentCapabilityModel:
        model = AssessmentService.get_capability_model(db, model_id)
        values = AssessmentService._validate_capability_model(db, body, model)
        return AssessmentCapabilityModelDAO.update(db, model, **values)

    @staticmethod
    def delete_capability_model(db: Session, model_id: int) -> None:
        model = AssessmentService.get_capability_model(db, model_id)
        paper_count = db.scalar(select(func.count()).select_from(AssessmentPaper).where(
            AssessmentPaper.capability_model_id == model.id
        )) or 0
        if paper_count:
            raise ValueError("能力模型已被试卷引用，不能删除；请停用该模型")
        AssessmentCapabilityModelDAO.delete(db, model)

    @staticmethod
    def _select_capability_questions(db: Session, model: AssessmentCapabilityModel) -> list[AssessmentQuestion]:
        if model.status != 1:
            raise ValueError("能力模型未启用")
        selected: list[AssessmentQuestion] = []
        selected_ids: set[int] = set()
        for rule in model.rules or []:
            stmt = select(AssessmentQuestion).where(
                AssessmentQuestion.status == 1,
                AssessmentQuestion.dimension == rule["dimension"],
            )
            if rule.get("bank_ids"):
                stmt = stmt.where(AssessmentQuestion.bank_id.in_(rule["bank_ids"]))
            if rule.get("types"):
                stmt = stmt.where(AssessmentQuestion.type.in_(rule["types"]))
            if rule.get("difficulties"):
                stmt = stmt.where(AssessmentQuestion.difficulty.in_(rule["difficulties"]))
            candidates = [question for question in db.scalars(stmt).all() if question.id not in selected_ids]
            count = int(rule["count"])
            if len(candidates) < count:
                raise ValueError(
                    f"能力模型维度“{rule['dimension']}”题量不足，需要 {count} 道，当前只有 {len(candidates)} 道"
                )
            picked = random.sample(candidates, count)
            selected.extend(picked)
            selected_ids.update(question.id for question in picked)
        return selected

    @staticmethod
    def _select_paper_questions(db: Session, body: PaperCreate) -> list[AssessmentQuestion]:
        mode_count = sum(bool(value) for value in (
            body.question_ids, body.random_rule, body.capability_model_id
        ))
        if mode_count > 1:
            raise ValueError("手动选题、随机组卷和能力模型组卷只能选择一种")

        if body.capability_model_id:
            model = AssessmentService.get_capability_model(db, body.capability_model_id)
            return AssessmentService._select_capability_questions(db, model)

        if body.question_ids:
            if len(body.question_ids) != len(set(body.question_ids)):
                raise ValueError("试卷不能包含重复题目")
            questions = list(db.scalars(select(AssessmentQuestion).where(
                AssessmentQuestion.id.in_(body.question_ids), AssessmentQuestion.status == 1
            )).all())
            by_id = {question.id: question for question in questions}
            if len(by_id) != len(body.question_ids):
                raise ValueError("存在不存在或已停用的题目")
            return [by_id[question_id] for question_id in body.question_ids]

        if not body.random_rule:
            raise ValueError("请提供题目 ID 或随机组卷规则")
        rule = RandomPaperRule.model_validate(body.random_rule)
        stmt = select(AssessmentQuestion).where(AssessmentQuestion.status == 1)
        if rule.bank_ids:
            stmt = stmt.where(AssessmentQuestion.bank_id.in_(rule.bank_ids))
        if rule.types:
            stmt = stmt.where(AssessmentQuestion.type.in_(rule.types))
        if rule.dimensions:
            stmt = stmt.where(AssessmentQuestion.dimension.in_(rule.dimensions))
        if rule.difficulties:
            stmt = stmt.where(AssessmentQuestion.difficulty.in_(rule.difficulties))
        candidates = list(db.scalars(stmt).all())
        if len(candidates) < rule.count:
            raise ValueError(f"符合条件的有效题目不足，需要 {rule.count} 道，当前只有 {len(candidates)} 道")
        return random.sample(candidates, rule.count)

    @staticmethod
    def create_paper(db: Session, body: PaperCreate) -> AssessmentPaper:
        questions = AssessmentService._select_paper_questions(db, body)
        if not questions:
            raise ValueError("试卷至少需要一道题目")
        bank_ids = sorted({question.bank_id for question in questions})
        generation_mode = "capability" if body.capability_model_id else (
            "random" if body.random_rule else "manual"
        )
        if body.capability_model_id:
            capability_model = AssessmentService.get_capability_model(db, body.capability_model_id)
            generation_rule = {
                "capability_model_id": capability_model.id,
                "model_name": capability_model.name,
                "position_id": capability_model.position_id,
                "position_level": capability_model.position_level,
                "rules": capability_model.rules,
            }
        else:
            generation_rule = body.random_rule
        paper = AssessmentPaperDAO.create(
            db,
            title=body.title,
            description=body.description,
            bank_ids=bank_ids,
            difficulty=body.difficulty,
            total_score=sum((Decimal(str(question.score)) for question in questions), Decimal("0.00")),
            duration=body.duration,
            status=1,
            generation_mode=generation_mode,
            capability_model_id=body.capability_model_id,
            generation_rule=generation_rule,
        )
        for index, question in enumerate(questions, start=1):
            db.add(PaperQuestion(
                paper_id=paper.id,
                question_id=question.id,
                sort=index,
                type_snapshot=question.type,
                content_snapshot=question.content,
                options_snapshot=question.options,
                answer_snapshot=question.answer,
                dimension_snapshot=question.dimension,
                score_snapshot=question.score,
            ))
        db.flush()
        return paper

    @staticmethod
    def list_papers(db: Session, *, keyword: str | None, status: int | None, page: int, page_size: int):
        return AssessmentPaperDAO.paged(db, keyword=keyword, status=status, page=page, page_size=page_size)

    @staticmethod
    def get_paper(db: Session, paper_id: int) -> AssessmentPaper:
        paper = AssessmentPaperDAO.get(db, paper_id)
        if not paper:
            raise LookupError("试卷不存在")
        return paper

    @staticmethod
    def update_paper(db: Session, paper_id: int, body: PaperUpdate) -> AssessmentPaper:
        paper = AssessmentService.get_paper(db, paper_id)
        if paper.status == 0 and body.status == 1:
            if not paper.question_links:
                raise ValueError("试卷没有题目，不能启用")
        return AssessmentPaperDAO.update(db, paper, **body.model_dump(exclude_unset=True))

    @staticmethod
    def delete_paper(db: Session, paper_id: int) -> None:
        paper = AssessmentService.get_paper(db, paper_id)
        if paper.results:
            raise ValueError("试卷已有测评记录，不能删除；请先停用试卷")
        AssessmentPaperDAO.delete(db, paper)

    @staticmethod
    def launch(db: Session, body: LaunchRequest, user: User | None = None) -> tuple[AssessmentBatch, list[AssessmentResult]]:
        paper = AssessmentService.get_paper(db, body.paper_id)
        if paper.status != 1:
            raise ValueError("试卷未启用")
        if not paper.question_links:
            raise ValueError("试卷没有题目")
        if len(body.talent_ids) != len(set(body.talent_ids)):
            raise ValueError("测试用户不能重复")
        users = list(db.scalars(select(User).where(User.id.in_(body.talent_ids), User.status == 1)).all())
        by_id = {user.id: user for user in users}
        if len(by_id) != len(body.talent_ids):
            raise ValueError("存在不存在或已停用的测试用户")

        started_at = body.started_at or datetime.now()
        deadline_at = body.deadline_at or started_at + timedelta(minutes=paper.duration)
        max_deadline = started_at + timedelta(minutes=paper.duration)
        if deadline_at <= started_at:
            raise ValueError("截止时间必须晚于开始时间")
        if deadline_at > max_deadline:
            raise ValueError("截止时间不能超过试卷答题时长")

        batch = AssessmentBatchDAO.create(
            db,
            batch_no=f"ASM-{datetime.now():%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}",
            name=body.batch_name or f"{paper.title} - {started_at:%Y-%m-%d %H:%M}",
            paper_id=paper.id,
            status=1,
            started_at=started_at,
            deadline_at=deadline_at,
            created_by=user.id if user else None,
        )
        results: list[AssessmentResult] = []
        for talent_id in body.talent_ids:
            result = AssessmentResultDAO.create(
                db,
                talent_id=talent_id,
                paper_id=paper.id,
                batch_id=batch.id,
                status=0,
                score=Decimal("0.00"),
                correct_count=0,
                started_at=started_at,
                deadline_at=deadline_at,
                answer_json={},
            )
            results.append(result)

        db.flush()
        for result in results:
            user = by_id[result.talent_id]
            try:
                with db.begin_nested():
                    MessageService.send(
                        db,
                        type_code="assess",
                        title=f"待完成测评：{paper.title}",
                        content=f"请在 {deadline_at:%Y-%m-%d %H:%M} 前完成测评。",
                        sender_id=None,
                        receiver_ids=[user.id],
                        biz_type="assessment_result",
                        biz_id=result.id,
                    )
            except Exception:
                # 通知不是测评主流程依赖，保留结果并等待后续补偿。
                continue
        return batch, results

    @staticmethod
    def _get_result(db: Session, result_id: int, user: User | None = None) -> AssessmentResult:
        result = AssessmentResultDAO.get(db, result_id)
        if not result:
            raise LookupError("测评记录不存在")
        if user and not user.is_super and result.talent_id != user.id:
            raise PermissionError("无权访问该测评记录")
        return result

    @staticmethod
    def _question_map(result: AssessmentResult) -> dict[int, PaperQuestion]:
        return {link.question_id: link for link in result.paper.question_links}

    @staticmethod
    def _validate_answer_value(link: PaperQuestion, value: Any) -> None:
        if link.type_snapshot == "multi" and not isinstance(value, list):
            raise ValueError(f"题目 {link.question_id} 的答案必须是数组")
        if link.type_snapshot in {"single", "judge"} and isinstance(value, list):
            raise ValueError(f"题目 {link.question_id} 的答案不能是数组")

    @staticmethod
    def _merge_answers(result: AssessmentResult, answers: dict[str, Any]) -> dict[str, Any]:
        question_map = AssessmentService._question_map(result)
        merged = dict(result.answer_json or {})
        for question_key, value in answers.items():
            try:
                question_id = int(question_key)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"无效题目 ID：{question_key}") from exc
            link = question_map.get(question_id)
            if not link:
                raise ValueError(f"题目 {question_id} 不属于当前测评试卷")
            AssessmentService._validate_answer_value(link, value)
            merged[str(question_id)] = value
        return merged

    @staticmethod
    def _ensure_answerable(result: AssessmentResult, user: User | None = None) -> AssessmentResult:
        if user and not user.is_super and result.talent_id != user.id:
            raise PermissionError("无权访问该测评记录")
        if result.status in {2, 3}:
            raise ValueError("测评已经交卷，不能继续作答")
        if result.status not in {0, 1}:
            raise ValueError("测评状态不允许作答")
        now = datetime.now()
        if result.deadline_at and now >= result.deadline_at:
            raise ValueError("测评已超过截止时间")
        if result.status == 0:
            result.status = 1
        return result

    @staticmethod
    def get_answer_snapshot(db: Session, result_id: int, user: User | None = None) -> dict:
        result = AssessmentService._get_result(db, result_id, user)
        AssessmentService._ensure_answerable(result, user)
        now = datetime.now()
        remaining = max(0, int((result.deadline_at - now).total_seconds())) if result.deadline_at else 0
        answers = dict(result.answer_json or {})
        questions = [
            {
                "question_id": link.question_id,
                "sort": link.sort,
                "type": link.type_snapshot,
                "content": link.content_snapshot,
                "options": link.options_snapshot,
                "dimension": link.dimension_snapshot,
                "score": link.score_snapshot,
                "user_answer": answers.get(str(link.question_id)),
            }
            for link in sorted(result.paper.question_links, key=lambda item: item.sort)
        ]
        db.flush()
        return {
            "result_id": result.id,
            "paper_id": result.paper_id,
            "talent_id": result.talent_id,
            "status": result.status,
            "started_at": result.started_at,
            "deadline_at": result.deadline_at,
            "server_time": now,
            "remaining_seconds": remaining,
            "answers": answers,
            "questions": questions,
        }

    @staticmethod
    def list_todo(db: Session, user: User) -> list[AssessmentResult]:
        talent_id = None if user.is_super else user.id
        return AssessmentResultDAO.paged(
            db, talent_id=talent_id, pending_only=True, page=1, page_size=200
        )[0]

    @staticmethod
    def get_answer_by_paper(db: Session, paper_id: int, user: User) -> dict:
        result = db.scalar(select(AssessmentResult).where(
            AssessmentResult.paper_id == paper_id,
            AssessmentResult.talent_id == user.id,
            AssessmentResult.status.in_([0, 1]),
        ).order_by(AssessmentResult.id.desc()))
        if not result:
            raise LookupError("没有该试卷的待测记录")
        return AssessmentService.get_answer_snapshot(db, result.id, user)

    @staticmethod
    def save_answers(db: Session, result_id: int, answers: dict[str, Any], user: User | None = None) -> dict:
        result = AssessmentResultDAO.get_for_update(db, result_id) or AssessmentService._get_result(db, result_id, user)
        AssessmentService._ensure_answerable(result, user)
        result.answer_json = AssessmentService._merge_answers(result, answers)
        db.flush()
        return AssessmentService.get_answer_snapshot(db, result_id, user)

    @staticmethod
    def record_answer_event(db: Session, result_id: int, event_type: str, detail: str,
                            source: str, user: User | None = None) -> AssessmentAnswerEvent:
        result = AssessmentService._get_result(db, result_id, user)
        if result.status in {2, 3}:
            raise ValueError("测评已经交卷，不能记录作答事件")
        event = AssessmentAnswerEvent(
            result_id=result.id,
            event_type=event_type,
            detail=detail,
            source=source,
        )
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def _answer_matches(question_type: str, expected: Any, actual: Any) -> bool:
        if actual is None:
            return False
        if question_type == "multi":
            if not isinstance(expected, list) or not isinstance(actual, list):
                return False
            return {str(value) for value in expected} == {str(value) for value in actual}
        if isinstance(expected, list):
            if len(expected) != 1:
                return False
            expected = expected[0]
        return str(expected) == str(actual)

    @staticmethod
    def submit(db: Session, result_id: int, answers: dict[str, Any] | None = None,
               user: User | None = None) -> tuple[AssessmentResult, list[AssessmentResultDetail]]:
        result = AssessmentResultDAO.get_for_update(db, result_id) or AssessmentService._get_result(db, result_id, user)
        if user and not user.is_super and result.talent_id != user.id:
            raise PermissionError("无权访问该测评记录")
        if result.status in {2, 3}:
            return result, AssessmentResultDetailDAO.list_by_result(db, result.id)
        AssessmentService._ensure_answerable(result, user)
        merged = AssessmentService._merge_answers(result, answers or {})
        now = datetime.now()
        if result.deadline_at and now >= result.deadline_at:
            raise ValueError("测评已超过截止时间，不能交卷")

        details: list[AssessmentResultDetail] = []
        total_score = Decimal("0.00")
        correct_count = 0
        for link in sorted(result.paper.question_links, key=lambda item: item.sort):
            actual = merged.get(str(link.question_id))
            correct = AssessmentService._answer_matches(link.type_snapshot, link.answer_snapshot, actual)
            score = Decimal(str(link.score_snapshot)) if correct else Decimal("0.00")
            details.append(AssessmentResultDetail(
                result_id=result.id,
                question_id=link.question_id,
                user_answer=actual,
                is_correct=1 if correct else 0,
                score=score,
            ))
            total_score += score
            correct_count += int(correct)

        result.answer_json = merged
        result.score = total_score
        result.correct_count = correct_count
        result.end_at = now
        result.status = 2
        db.add_all(details)
        db.flush()
        return result, details

    @staticmethod
    def get_result_detail(db: Session, result_id: int, user: User | None = None) -> dict:
        result = AssessmentService._get_result(db, result_id, user)
        row = AssessmentResultDAO.get_with_user_and_paper(db, result_id)
        details = AssessmentResultDetailDAO.list_by_result(db, result_id)
        events = AssessmentAnswerEventDAO.list_by_result(db, result_id)
        return {
            "result": result,
            "details": details,
            "events": events,
            "talent_name": row[1] if row else None,
            "paper_title": row[2] if row else None,
        }

    @staticmethod
    def list_results(db: Session, *, talent_id: int | None, paper_id: int | None,
                     batch_id: int | None, status: int | None, page: int, page_size: int):
        return AssessmentResultDAO.paged_with_names(
            db, talent_id=talent_id, paper_id=paper_id, batch_id=batch_id, status=status,
            page=page, page_size=page_size,
        )

    @staticmethod
    def list_batches(db: Session, *, paper_id: int | None, status: int | None,
                     page: int, page_size: int):
        return AssessmentBatchDAO.paged(
            db, paper_id=paper_id, status=status, page=page, page_size=page_size
        )

    @staticmethod
    def get_batch(db: Session, batch_id: int) -> AssessmentBatch:
        batch = AssessmentBatchDAO.get(db, batch_id)
        if not batch:
            raise LookupError("测评批次不存在")
        return batch

    @staticmethod
    def statistics(db: Session, *, talent_id: int | None, paper_id: int | None,
                   batch_id: int | None = None) -> dict:
        # SQL 聚合（AssessmentResultDAO.statistics），避免全量加载 + Python 聚合
        agg = AssessmentResultDAO.statistics(
            db, talent_id=talent_id, paper_id=paper_id, batch_id=batch_id
        )
        total_results = agg["total_results"]
        completed_count = agg["completed_results"]
        avg_score = agg["average_score"] if agg["average_score"] is not None else Decimal("0.00")
        avg_rate = agg["average_rate"] if agg["average_rate"] is not None else Decimal("0.00")
        pass_count = agg["pass_count"]
        dimensions = [
            {
                "dimension": d["dimension"],
                "score": Decimal(str(d["score"])),
                "total_score": Decimal(str(d["total_score"])),
                "accuracy": Decimal(str(
                    d["score"] / d["total_score"] if d["total_score"] else 0
                )).quantize(Decimal("0.01")),
                "result_count": d["result_count"],
                "question_count": d["question_count"],
            }
            for d in agg["dimensions"]
        ]
        return {
            "total_results": total_results,
            "completed_results": completed_count,
            "average_score": avg_score,
            "average_rate": avg_rate,
            "pass_count": pass_count,
            "pass_rate": Decimal(str(pass_count / completed_count if completed_count else 0)).quantize(Decimal("0.01")),
            "dimensions": dimensions,
        }

    @staticmethod
    def batch_statistics(db: Session, *, batch_id: int | None = None,
                         paper_id: int | None = None) -> list[dict]:
        # SQL 聚合（AssessmentBatchDAO.batch_statistics），避免逐批次全量拉取 + Python 聚合
        rows = AssessmentBatchDAO.batch_statistics(db, batch_id=batch_id, paper_id=paper_id)
        items = []
        for row in rows:
            total = int(row["total_results"] or 0)
            completed_count = int(row["completed_results"] or 0)
            pass_count = int(row["pass_count"] or 0)
            avg = row["avg_score"]
            items.append({
                "batch_id": row["batch_id"],
                "batch_no": row["batch_no"],
                "batch_name": row["name"],
                "paper_id": row["paper_id"],
                "total_results": total,
                "completed_results": completed_count,
                "completion_rate": Decimal(str(
                    completed_count / total if total else 0
                )).quantize(Decimal("0.01")),
                "pass_count": pass_count,
                "pass_rate": Decimal(str(
                    pass_count / completed_count if completed_count else 0
                )).quantize(Decimal("0.01")),
                "average_score": Decimal(str(avg if avg is not None else 0)).quantize(Decimal("0.01")),
            })
        return items

    @staticmethod
    def question_statistics(db: Session, *, paper_id: int | None = None,
                            batch_id: int | None = None) -> list[dict]:
        results = AssessmentResultDAO.list_completed(
            db, paper_id=paper_id, batch_id=batch_id
        )
        buckets: dict[int, dict[str, Any]] = {}
        for result in results:
            details = {detail.question_id: detail for detail in result.details}
            for link in result.paper.question_links:
                bucket = buckets.setdefault(link.question_id, {
                    "question_id": link.question_id,
                    "content": link.content_snapshot,
                    "dimension": link.dimension_snapshot,
                    "attempt_count": 0,
                    "answered_count": 0,
                    "correct_count": 0,
                    "score_sum": Decimal("0.00"),
                    "total_score": Decimal("0.00"),
                })
                bucket["attempt_count"] += 1
                bucket["total_score"] += Decimal(str(link.score_snapshot))
                detail = details.get(link.question_id)
                if not detail:
                    continue
                answer = detail.user_answer
                if answer is not None and answer != [] and answer != "":
                    bucket["answered_count"] += 1
                bucket["correct_count"] += int(detail.is_correct)
                bucket["score_sum"] += Decimal(str(detail.score))

        items = []
        for question_id, bucket in sorted(buckets.items()):
            attempts = bucket["attempt_count"]
            items.append({
                "question_id": question_id,
                "content": bucket["content"],
                "dimension": bucket["dimension"],
                "attempt_count": attempts,
                "answered_count": bucket["answered_count"],
                "correct_count": bucket["correct_count"],
                "accuracy": Decimal(str(
                    bucket["correct_count"] / attempts if attempts else 0
                )).quantize(Decimal("0.01")),
                "average_score": (
                    bucket["score_sum"] / attempts if attempts else Decimal("0.00")
                ),
                "total_score": bucket["total_score"],
            })
        return items

    @staticmethod
    def get_report(db: Session, result_id: int, user: User | None = None) -> dict:
        result = AssessmentService._get_result(db, result_id, user)
        if result.status not in {2, 3}:
            raise ValueError("测评尚未交卷，不能生成报告")
        if result.report_json:
            return result.report_json
        return AssessmentReportService.generate(db, result)

    @staticmethod
    def link_training(db: Session, result_id: int, user: User | None = None):
        result = AssessmentService._get_result(db, result_id, user)
        if result.status != 3 or not result.report_json:
            raise ValueError("请先生成测评报告")
        return AssessmentReportService.run_training_graph(db, result)

    @staticmethod
    def get_training_link(db: Session, result_id: int, user: User | None = None):
        result = AssessmentService._get_result(db, result_id, user)
        return AssessmentReportService.get_training_link(db, result.id)

    @staticmethod
    def retry_training_link(db: Session, result_id: int, user: User | None = None):
        result = AssessmentService._get_result(db, result_id, user)
        if result.status != 3 or not result.report_json:
            raise ValueError("请先生成测评报告")
        return AssessmentReportService.retry_training_link(db, result)

    @staticmethod
    def get_agent_task(db: Session, task_id: int, user: User | None = None):
        from app.dao.agent import AgentTaskDAO

        task = AgentTaskDAO.get(db, task_id)
        if not task:
            raise LookupError("Agent 任务不存在")
        if user and not user.is_super:
            result = task.result
            if not result or result.talent_id != user.id:
                raise PermissionError("无权访问该 Agent 任务")
        return task

    @staticmethod
    def list_agent_tasks(db: Session, result_id: int | None = None, user: User | None = None):
        from app.dao.agent import AgentTaskDAO

        if result_id is not None:
            result = db.get(AssessmentResult, result_id)
            if not result:
                raise LookupError("测评记录不存在")
            if user and not user.is_super and result.talent_id != user.id:
                raise PermissionError("无权访问该 Agent 任务")
            return AgentTaskDAO.list_by_result(db, result_id)
        if user and not user.is_super:
            from app.dao.assessment import AssessmentResultDAO

            result_ids = [item.id for item in AssessmentResultDAO.list_by_talent(db, user.id)]
            if not result_ids:
                return []
            return list(db.query(AgentTaskDAO.__model__).filter(
                AgentTaskDAO.__model__.result_id.in_(result_ids)
            ).order_by(AgentTaskDAO.__model__.id.desc()).limit(200))
        return list(db.query(AgentTaskDAO.__model__).order_by(AgentTaskDAO.__model__.id.desc()).limit(200))
