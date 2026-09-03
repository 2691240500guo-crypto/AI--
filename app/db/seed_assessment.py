"""C 智能测评本地演示数据，重复执行保持幂等。"""

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.assessment_role_questions import DIMENSIONS, ROLE_QUESTION_SETS
from app.models.assessment import (
    AssessmentBatch,
    AssessmentCapabilityModel,
    AssessmentPaper,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentResultDetail,
    AssessmentTrainingOutbox,
    PaperQuestion,
    QuestionBank,
)
from app.models.user import User
from app.models.talent import Talent
from app.services.assessment_report_service import AssessmentReportService


DEMO_USERNAME = "assessment_demo"
DEMO_BANK_NAME = "本地演示能力题库"
DEMO_PAPER_TITLE = "本地演示综合测评"
TEST_USERNAME_PREFIX = "c_demo_"
TEST_BANK_PREFIX = "C智能测评演示题库"
TEST_PAPER_PREFIX = "C智能测评演示试卷"


def _ensure_employee_identity(db: Session, user: User, *, name: str) -> Talent:
    """为演示员工补齐人才档案与账号锚点，兼容已经存在的旧种子账号。"""
    talent = db.get(Talent, user.talent_id) if user.talent_id else None
    if talent is None:
        talent = db.scalar(select(Talent).where(Talent.name == name, Talent.phone == user.phone)) if user.phone else None
    if talent is None:
        talent = Talent(
            name=name,
            phone=user.phone,
            email=user.email,
            dept_id=user.dept_id,
            status=1,
            resume_source="seed",
            data_quality="good",
        )
        db.add(talent)
        db.flush()
    user.talent_id = talent.id
    user.user_type = "employee"
    if not user.emp_no:
        user.emp_no = user.username
    return talent

TEST_QUESTIONS = [
    {
        "type": "single",
        "content": "项目启动阶段最先应明确什么？",
        "options": ["项目目标", "庆祝方式", "办公地点", "会议零食"],
        "answer": ["项目目标"],
        "dimension": "项目管理",
        "difficulty": 1,
    },
    {
        "type": "multi",
        "content": "以下哪些属于有效的风险管理动作？",
        "options": ["识别风险", "评估影响", "制定应对措施", "忽略风险"],
        "answer": ["识别风险", "评估影响", "制定应对措施"],
        "dimension": "风险管理",
        "difficulty": 2,
    },
    {
        "type": "judge",
        "content": "测评成绩应由服务端根据答案重新计算。",
        "options": ["正确", "错误"],
        "answer": "正确",
        "dimension": "数字化素养",
        "difficulty": 1,
    },
    {
        "type": "single",
        "content": "发现数据指标异常时，第一步应该做什么？",
        "options": ["核查数据口径", "直接删除数据", "忽略异常", "立即发布结论"],
        "answer": ["核查数据口径"],
        "dimension": "数据分析",
        "difficulty": 2,
    },
    {
        "type": "multi",
        "content": "以下哪些做法有助于保护账号安全？",
        "options": ["使用复杂密码", "开启多因素认证", "定期检查登录记录", "多人共用账号"],
        "answer": ["使用复杂密码", "开启多因素认证", "定期检查登录记录"],
        "dimension": "信息安全",
        "difficulty": 3,
    },
    {
        "type": "judge",
        "content": "敏感个人信息可以在未授权的情况下导出给外部人员。",
        "options": ["正确", "错误"],
        "answer": "错误",
        "dimension": "合规意识",
        "difficulty": 3,
    },
    {
        "type": "single",
        "content": "敏捷迭代中，最适合持续确认方向的会议是？",
        "options": ["迭代评审", "年终聚餐", "设备盘点", "门禁检查"],
        "answer": ["迭代评审"],
        "dimension": "敏捷协作",
        "difficulty": 2,
    },
    {
        "type": "multi",
        "content": "高质量需求通常应包含哪些内容？",
        "options": ["业务目标", "验收标准", "边界条件", "只写一句口号"],
        "answer": ["业务目标", "验收标准", "边界条件"],
        "dimension": "需求分析",
        "difficulty": 4,
    },
    {
        "type": "judge",
        "content": "数据可视化图表应服务于业务问题，而不是只追求装饰效果。",
        "options": ["正确", "错误"],
        "answer": "正确",
        "dimension": "数据表达",
        "difficulty": 4,
    },
    {
        "type": "single",
        "content": "上线前发现高风险缺陷，最合理的处理方式是？",
        "options": ["阻断上线并修复", "隐藏缺陷", "删除测试记录", "交给用户发现"],
        "answer": ["阻断上线并修复"],
        "dimension": "质量保障",
        "difficulty": 5,
    },
]


def seed_assessment(db: Session) -> None:
    demo_user = db.scalar(select(User).where(User.username == DEMO_USERNAME))
    if not demo_user:
        demo_user = User(
            username=DEMO_USERNAME,
            password=hash_password("assessment123"),
            nickname="测评演示用户",
            dept_id=1,
            status=1,
            is_super=0,
        )
        db.add(demo_user)
        db.flush()
    _ensure_employee_identity(db, demo_user, name="测评演示人才")

    bank = db.scalar(select(QuestionBank).where(QuestionBank.name == DEMO_BANK_NAME))
    if not bank:
        bank = QuestionBank(
            name=DEMO_BANK_NAME,
            description="用于 C 智能测评本地闭环演示，覆盖三种题型。",
            status=1,
        )
        db.add(bank)
        db.flush()

    questions = list(db.scalars(select(AssessmentQuestion).where(AssessmentQuestion.bank_id == bank.id)).all())
    if not questions:
        questions = [
            AssessmentQuestion(
                bank_id=bank.id,
                type="single",
                content="项目启动阶段最先应明确什么？",
                options=["项目目标", "庆祝方式", "办公地点", "会议零食"],
                answer=["项目目标"],
                dimension="项目管理",
                difficulty=1,
                score=Decimal("10.00"),
                status=1,
            ),
            AssessmentQuestion(
                bank_id=bank.id,
                type="multi",
                content="以下哪些属于有效的风险管理动作？",
                options=["识别风险", "评估影响", "制定应对措施", "忽略风险"],
                answer=["识别风险", "评估影响", "制定应对措施"],
                dimension="风险管理",
                difficulty=2,
                score=Decimal("10.00"),
                status=1,
            ),
            AssessmentQuestion(
                bank_id=bank.id,
                type="judge",
                content="测评成绩应由服务端根据答案重新计算。",
                options=["正确", "错误"],
                answer="正确",
                dimension="数字化素养",
                difficulty=1,
                score=Decimal("10.00"),
                status=1,
            ),
        ]
        db.add_all(questions)
        db.flush()

    paper = db.scalar(select(AssessmentPaper).where(AssessmentPaper.title == DEMO_PAPER_TITLE))
    if not paper:
        paper = AssessmentPaper(
            title=DEMO_PAPER_TITLE,
            description="C 智能测评本地演示试卷。",
            bank_ids=[bank.id],
            difficulty=2,
            total_score=sum((Decimal(str(question.score)) for question in questions), Decimal("0.00")),
            duration=60,
            status=1,
        )
        db.add(paper)
        db.flush()
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

    db.commit()

    _seed_test_data(db)
    _seed_role_assessments(db)
    _seed_capability_models(db)


def _answers_match(question_type: str, expected, actual) -> bool:
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


def _seed_test_data(db: Session) -> None:
    """创建管理端可操作的 C 智能测评闭环样本。"""
    now = datetime.now()
    users: list[User] = []
    papers: list[AssessmentPaper] = []
    questions: list[AssessmentQuestion] = []

    for index, question_data in enumerate(TEST_QUESTIONS, start=1):
        username = f"{TEST_USERNAME_PREFIX}{index:02d}"
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            user = User(
                username=username,
                password=hash_password("assessment123"),
                nickname=f"测评演示用户{index:02d}",
                dept_id=1,
                status=1,
                is_super=0,
            )
            db.add(user)
            db.flush()
        _ensure_employee_identity(db, user, name=f"测评演示人才{index:02d}")
        users.append(user)

        bank_name = f"{TEST_BANK_PREFIX}{index:02d}"
        bank = db.scalar(select(QuestionBank).where(QuestionBank.name == bank_name))
        if not bank:
            bank = QuestionBank(
                name=bank_name,
                description=f"C 智能测评演示题库 {index:02d}，用于验证筛选与组卷。",
                status=1,
            )
            db.add(bank)
            db.flush()

        question = db.scalar(select(AssessmentQuestion).where(
            AssessmentQuestion.bank_id == bank.id,
            AssessmentQuestion.content == question_data["content"],
        ))
        if not question:
            question = AssessmentQuestion(
                bank_id=bank.id,
                type=question_data["type"],
                content=question_data["content"],
                options=question_data["options"],
                answer=question_data["answer"],
                dimension=question_data["dimension"],
                difficulty=question_data["difficulty"],
                score=Decimal("10.00"),
                status=1,
            )
            db.add(question)
            db.flush()
        questions.append(question)

        paper_title = f"{TEST_PAPER_PREFIX}{index:02d}"
        paper = db.scalar(select(AssessmentPaper).where(AssessmentPaper.title == paper_title))
        if not paper:
            paper = AssessmentPaper(
                title=paper_title,
                description=f"C 智能测评演示试卷 {index:02d}，可独立发起答题。",
                bank_ids=[bank.id],
                difficulty=question.difficulty,
                total_score=Decimal("10.00"),
                duration=60,
                status=1,
            )
            db.add(paper)
            db.flush()
        if not db.scalar(select(PaperQuestion).where(
            PaperQuestion.paper_id == paper.id,
            PaperQuestion.question_id == question.id,
        )):
            db.add(PaperQuestion(
                paper_id=paper.id,
                question_id=question.id,
                sort=1,
                type_snapshot=question.type,
                content_snapshot=question.content,
                options_snapshot=question.options,
                answer_snapshot=question.answer,
                dimension_snapshot=question.dimension,
                score_snapshot=question.score,
            ))
            db.flush()
        batch = db.scalar(select(AssessmentBatch).where(
            AssessmentBatch.batch_no == f"C-DEMO-BATCH-{index:02d}"
        ))
        if not batch:
            batch = AssessmentBatch(
                batch_no=f"C-DEMO-BATCH-{index:02d}",
                name=f"C 智能测评演示批次 {index:02d}",
                paper_id=paper.id,
                status=1,
                started_at=now - timedelta(minutes=index * 3),
                deadline_at=now + timedelta(hours=2),
            )
            db.add(batch)
            db.flush()
        papers.append(paper)

    for index, (user, paper, question) in enumerate(zip(users, papers, questions), start=1):
        result = db.scalar(select(AssessmentResult).where(
            AssessmentResult.talent_id == user.talent_id,
            AssessmentResult.paper_id == paper.id,
        ))
        if result is None:
            result = db.scalar(select(AssessmentResult).where(
                AssessmentResult.user_id == user.id,
                AssessmentResult.paper_id == paper.id,
            ))
        if result:
            if result.batch_id is None:
                result.batch_id = db.scalar(select(AssessmentBatch.id).where(
                    AssessmentBatch.batch_no == f"C-DEMO-BATCH-{index:02d}"
                ))
            continue

        status = (index - 1) % 4
        started_at = now - timedelta(minutes=index * 3)
        result = AssessmentResult(
            talent_id=user.talent_id,
            user_id=user.id,
            paper_id=paper.id,
            batch_id=db.scalar(select(AssessmentBatch.id).where(
                AssessmentBatch.batch_no == f"C-DEMO-BATCH-{index:02d}"
            )),
            status=status,
            score=Decimal("0.00"),
            correct_count=0,
            started_at=started_at if status else None,
            deadline_at=now + timedelta(hours=2),
            answer_json={},
        )
        db.add(result)
        db.flush()
        if status == 0:
            continue

        answer = question.answer
        if index % 3 == 0:
            if question.type == "multi":
                answer = [str(answer[0])] if isinstance(answer, list) else answer
            elif question.type == "single":
                answer = "非标准答案"
            else:
                answer = "错误" if answer == "正确" else "正确"
        result.answer_json = {str(question.id): answer}
        if status == 1:
            continue

        is_correct = _answers_match(question.type, question.answer, answer)
        result.score = question.score if is_correct else Decimal("0.00")
        result.correct_count = int(is_correct)
        result.end_at = started_at + timedelta(minutes=12)
        db.add(AssessmentResultDetail(
            result_id=result.id,
            question_id=question.id,
            user_answer=answer,
            is_correct=int(is_correct),
            score=result.score,
        ))
        db.flush()
        if status == 3:
            result.report_json = AssessmentReportService.build_local_report(result)
            result.report_source = "local"
            db.add(AssessmentTrainingOutbox(
                result_id=result.id,
                weak_dimensions=result.report_json["weaknesses"],
                status="pending",
                retry_count=0,
                error_message="培训模块尚未接入，等待后续处理",
            ))
            db.flush()

    db.commit()


def _wrong_answer(question: AssessmentQuestion):
    if question.type == "multi":
        return [question.answer[0]] if isinstance(question.answer, list) and question.answer else []
    if question.type == "judge":
        return "错误" if question.answer == "正确" else "正确"
    expected = question.answer[0] if isinstance(question.answer, list) and question.answer else question.answer
    return next((option for option in question.options or [] if option != expected), "非标准答案")


def _seed_role_assessments(db: Session) -> None:
    """创建四类岗位的五维题库、试卷和可视化结果。"""
    now = datetime.now()
    correct_targets = {
        "hr": [3, 2, 3, 2, 1],
        "sales": [2, 3, 2, 3, 1],
        "equipment_engineer": [3, 2, 2, 3, 3],
        "planner": [2, 3, 3, 2, 2],
    }

    for role_key, role_data in ROLE_QUESTION_SETS.items():
        username = f"assessment_{role_key}"
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            user = User(
                username=username,
                password=hash_password("assessment123"),
                nickname=f"{role_data['role_name']}岗位演示人员",
                dept_id=1,
                status=1,
                is_super=0,
            )
            db.add(user)
            db.flush()
        talent = _ensure_employee_identity(db, user, name=f"{role_data['role_name']}岗位演示人才")

        bank = db.scalar(select(QuestionBank).where(QuestionBank.name == role_data["bank_name"]))
        if not bank:
            bank = QuestionBank(
                name=role_data["bank_name"],
                description=f"{role_data['role_name']}岗位五维能力题库，共15题。",
                status=1,
            )
            db.add(bank)
            db.flush()

        questions = []
        for item in role_data["questions"]:
            question = db.scalar(select(AssessmentQuestion).where(
                AssessmentQuestion.bank_id == bank.id,
                AssessmentQuestion.content == item["content"],
            ))
            if not question:
                question = AssessmentQuestion(
                    bank_id=bank.id,
                    type=item["type"],
                    content=item["content"],
                    options=item["options"],
                    answer=item["answer"],
                    dimension=item["dimension"],
                    difficulty=item["difficulty"],
                    score=Decimal("10.00"),
                    status=1,
                )
                db.add(question)
                db.flush()
            questions.append(question)

        model = db.scalar(select(AssessmentCapabilityModel).where(
            AssessmentCapabilityModel.name == role_data["model_name"]
        ))
        if not model:
            model = AssessmentCapabilityModel(
                name=role_data["model_name"],
                description=f"{role_data['role_name']}岗位专业、业务、协作、执行与风控五维模型。",
                rules=[{
                    "dimension": dimension,
                    "count": 3,
                    "bank_ids": [bank.id],
                    "types": [],
                    "difficulties": [],
                } for dimension in DIMENSIONS],
                status=1,
            )
            db.add(model)
            db.flush()

        paper = db.scalar(select(AssessmentPaper).where(
            AssessmentPaper.title == role_data["paper_title"]
        ))
        if not paper:
            paper = AssessmentPaper(
                title=role_data["paper_title"],
                description=f"{role_data['role_name']}岗位五维雷达演示试卷。",
                bank_ids=[bank.id],
                difficulty=3,
                total_score=Decimal("150.00"),
                duration=45,
                status=1,
                generation_mode="capability",
                capability_model_id=model.id,
                generation_rule={"dimensions": DIMENSIONS, "questions_per_dimension": 3},
            )
            db.add(paper)
            db.flush()

        for sort, question in enumerate(questions, start=1):
            if db.scalar(select(PaperQuestion).where(
                PaperQuestion.paper_id == paper.id,
                PaperQuestion.question_id == question.id,
            )):
                continue
            db.add(PaperQuestion(
                paper_id=paper.id,
                question_id=question.id,
                sort=sort,
                type_snapshot=question.type,
                content_snapshot=question.content,
                options_snapshot=question.options,
                answer_snapshot=question.answer,
                dimension_snapshot=question.dimension,
                score_snapshot=question.score,
            ))
        db.flush()

        batch_no = f"C-ROLE-{role_key.upper()}"
        batch = db.scalar(select(AssessmentBatch).where(AssessmentBatch.batch_no == batch_no))
        if not batch:
            batch = AssessmentBatch(
                batch_no=batch_no,
                name=f"{role_data['role_name']}岗位能力演示批次",
                paper_id=paper.id,
                status=2,
                started_at=now - timedelta(days=1),
                deadline_at=now + timedelta(days=7),
            )
            db.add(batch)
            db.flush()

        result = db.scalar(select(AssessmentResult).where(
            AssessmentResult.talent_id == talent.id,
            AssessmentResult.paper_id == paper.id,
        ))
        if result:
            continue

        started_at = now - timedelta(hours=2)
        result = AssessmentResult(
            talent_id=talent.id,
            user_id=user.id,
            paper_id=paper.id,
            batch_id=batch.id,
            status=3,
            score=Decimal("0.00"),
            correct_count=0,
            started_at=started_at,
            deadline_at=now + timedelta(days=7),
            end_at=started_at + timedelta(minutes=28),
            answer_json={},
            report_source="local",
        )
        db.add(result)
        db.flush()

        dimension_seen = {dimension: 0 for dimension in DIMENSIONS}
        answers = {}
        details = []
        total_score = Decimal("0.00")
        correct_count = 0
        targets = dict(zip(DIMENSIONS, correct_targets[role_key]))
        for question in questions:
            dimension_seen[question.dimension] += 1
            is_correct = dimension_seen[question.dimension] <= targets[question.dimension]
            answer = question.answer if is_correct else _wrong_answer(question)
            answers[str(question.id)] = answer
            score = question.score if is_correct else Decimal("0.00")
            total_score += score
            correct_count += int(is_correct)
            details.append(AssessmentResultDetail(
                result_id=result.id,
                question_id=question.id,
                user_answer=answer,
                is_correct=int(is_correct),
                score=score,
            ))
        result.answer_json = answers
        result.score = total_score
        result.correct_count = correct_count
        db.add_all(details)
        db.commit()

        result = db.scalar(select(AssessmentResult).where(AssessmentResult.id == result.id))
        result.report_json = AssessmentReportService.build_local_report(result)
        db.add(AssessmentTrainingOutbox(
            result_id=result.id,
            weak_dimensions=result.report_json["weaknesses"],
            status="pending",
            retry_count=0,
            error_message="培训模块尚未接入，等待后续处理",
        ))
        db.commit()


def _seed_capability_models(db: Session) -> None:
    """为能力模型和自动组卷提供可直接演示的规则样本。"""
    question_by_dimension = {
        question.dimension: question
        for question in db.scalars(select(AssessmentQuestion).where(AssessmentQuestion.status == 1)).all()
    }
    demo_models = [
        ("C演示基础能力模型", "覆盖项目管理与数字化素养。", ["项目管理", "数字化素养"]),
        ("C演示数据安全模型", "覆盖数据分析、信息安全与合规意识。", ["数据分析", "信息安全", "合规意识"]),
        ("C演示综合能力模型", "覆盖十个演示维度，用于验证多维度自动组卷。", list(TEST_QUESTIONS[i]["dimension"] for i in range(len(TEST_QUESTIONS)))),
    ]
    for name, description, dimensions in demo_models:
        if db.scalar(select(AssessmentCapabilityModel).where(AssessmentCapabilityModel.name == name)):
            continue
        rules = [
            {
                "dimension": dimension,
                "count": 1,
                "bank_ids": [question_by_dimension[dimension].bank_id],
                "types": [],
                "difficulties": [],
            }
            for dimension in dimensions
            if dimension in question_by_dimension
        ]
        if rules:
            db.add(AssessmentCapabilityModel(
                name=name,
                description=description,
                rules=rules,
                status=1,
            ))
    db.commit()
