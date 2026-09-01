"""造演示数据：40 道新题目 + 50 条组卷（供组卷管理/发起测评演示）。

用法（项目根目录）：
    python scripts/seed_assessment_data.py
"""
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from app.db.session import SessionLocal
from app.models.assessment import Paper, PaperQuestion, Question

random.seed(42)

# ---------- 40 道新题目（覆盖 6 个维度） ----------
NEW_QUESTIONS = [
    # 技术
    ("single", "Python 中用于定义不可变序列的内置类型是？", [{"key":"A","text":"list"},{"key":"B","text":"tuple"},{"key":"C","text":"dict"},{"key":"D","text":"set"}], "B", "技术", 2, 10),
    ("single", "HTTP 状态码 200 表示？", [{"key":"A","text":"请求成功"},{"key":"B","text":"重定向"},{"key":"C","text":"服务器错误"},{"key":"D","text":"未授权"}], "A", "技术", 1, 5),
    ("single", "SQL 中用于分组统计的关键字是？", [{"key":"A","text":"ORDER BY"},{"key":"B","text":"GROUP BY"},{"key":"C","text":"HAVING"},{"key":"D","text":"LIMIT"}], "B", "技术", 2, 10),
    ("multi", "以下哪些是关系型数据库？", [{"key":"A","text":"MySQL"},{"key":"B","text":"PostgreSQL"},{"key":"C","text":"Redis"},{"key":"D","text":"MongoDB"}], "A,B", "技术", 2, 10),
    ("judge", "FastAPI 基于 Starlette 构建。", None, "true", "技术", 1, 5),
    ("single", "Git 中用于切换分支的命令是？", [{"key":"A","text":"git commit"},{"key":"B","text":"git checkout"},{"key":"C","text":"git push"},{"key":"D","text":"git merge"}], "B", "技术", 1, 5),
    ("single", "Docker 镜像的构建文件通常命名为？", [{"key":"A","text":"Dockerfile"},{"key":"B","text":"docker.conf"},{"key":"C","text":"container.yml"},{"key":"D","text":"build.json"}], "A", "技术", 2, 10),
    ("judge", "Redis 是纯内存数据库，重启后数据必然丢失。", None, "false", "技术", 2, 5),
    ("single", "以下哪个不是 Python 的 Web 框架？", [{"key":"A","text":"Django"},{"key":"B","text":"Flask"},{"key":"C","text":"Spring"},{"key":"D","text":"FastAPI"}], "C", "技术", 2, 10),
    ("multi", "属于前端框架的有？", [{"key":"A","text":"Vue"},{"key":"B","text":"React"},{"key":"C","text":"Angular"},{"key":"D","text":"Spring"}], "A,B,C", "技术", 2, 10),
    # 沟通
    ("single", "有效沟通的第一步是？", [{"key":"A","text":"倾听"},{"key":"B","text":"表达"},{"key":"C","text":"记录"},{"key":"D","text":"反驳"}], "A", "沟通", 1, 10),
    ("judge", "跨部门协作中，主动同步进度有助于减少信息差。", None, "true", "沟通", 1, 5),
    ("single", "向上汇报时，最推荐的结构是？", [{"key":"A","text":"先讲过程再讲结果"},{"key":"B","text":"先讲结论再补充依据"},{"key":"C","text":"只讲遇到的问题"},{"key":"D","text":"只讲自己做了什么"}], "B", "沟通", 2, 10),
    ("single", "收到批评意见时，恰当的做法是？", [{"key":"A","text":"立即反驳"},{"key":"B","text":"冷静分析合理性"},{"key":"C","text":"不予理睬"},{"key":"D","text":"私下抱怨"}], "B", "沟通", 1, 5),
    ("multi", "以下属于非语言沟通的有？", [{"key":"A","text":"眼神交流"},{"key":"B","text":"肢体动作"},{"key":"C","text":"语气语调"},{"key":"D","text":"书面邮件"}], "A,B,C", "沟通", 2, 10),
    # 逻辑
    ("single", "如果所有 A 都是 B，且某物是 A，则可以推出？", [{"key":"A","text":"某物是 B"},{"key":"B","text":"某物不是 B"},{"key":"C","text":"所有 B 都是 A"},{"key":"D","text":"无法判断"}], "A", "逻辑", 2, 10),
    ("judge", "归纳推理的结论必然为真。", None, "false", "逻辑", 2, 5),
    ("single", "数列 1, 4, 9, 16, 25 的下一项是？", [{"key":"A","text":"30"},{"key":"B","text":"36"},{"key":"C","text":"40"},{"key":"D","text":"49"}], "B", "逻辑", 1, 5),
    ("single", "甲比乙高，丙比乙矮，则？", [{"key":"A","text":"甲比丙高"},{"key":"B","text":"丙比甲高"},{"key":"C","text":"甲乙一样高"},{"key":"D","text":"无法比较甲丙"}], "A", "逻辑", 2, 10),
    ("multi", "以下哪些属于演绎推理？", [{"key":"A","text":"三段论"},{"key":"B","text":"假言推理"},{"key":"C","text":"由样本推断总体"},{"key":"D","text":"类比推理"}], "A,B", "逻辑", 3, 10),
    # 管理
    ("single", "SMART 原则中 M 代表？", [{"key":"A","text":"Measurable 可衡量"},{"key":"B","text":"Manageable 可管理"},{"key":"C","text":"Motivating 可激励"},{"key":"D","text":"Moderate 适度"}], "A", "管理", 2, 10),
    ("judge", "OKR 中的 O 是 Key Results 的缩写。", None, "false", "管理", 2, 5),
    ("single", "项目管理中「关键路径」指的是？", [{"key":"A","text":"耗时最长的路径"},{"key":"B","text":"风险最高的路径"},{"key":"C","text":"最早开始的路径"},{"key":"D","text":"任意路径"}], "A", "管理", 3, 10),
    ("multi", "以下属于敏捷开发实践的有？", [{"key":"A","text":"每日站会"},{"key":"B","text":"Sprint 回顾"},{"key":"C","text":"需求冻结"},{"key":"D","text":"看板管理"}], "A,B,D", "管理", 2, 10),
    ("single", "团队冲突管理的最佳目标是？", [{"key":"A","text":"消除所有冲突"},{"key":"B","text":"建设性解决冲突"},{"key":"C","text":"忽略冲突"},{"key":"D","text":"回避冲突"}], "B", "管理", 2, 10),
    # 英语
    ("single", "The project was completed ______ time.", [{"key":"A","text":"on"},{"key":"B","text":"in"},{"key":"C","text":"at"},{"key":"D","text":"by"}], "A", "英语", 2, 5),
    ("judge", "\"Deliverable\" 指的是可交付成果。", None, "true", "英语", 2, 5),
    ("single", "Choose the correct word: This is the ______ report.", [{"key":"A","text":"final"},{"key":"B","text":"finally"},{"key":"C","text":"finish"},{"key":"D","text":"finished"}], "A", "英语", 1, 5),
    ("single", "\"Synergy\" most likely means ______.", [{"key":"A","text":"协同效应"},{"key":"B","text":"竞争"},{"key":"C","text":"独立"},{"key":"D","text":"冲突"}], "A", "英语", 3, 5),
    # 综合
    ("single", "以下哪个能力对晋升管理岗最重要？", [{"key":"A","text":"技术深度"},{"key":"B","text":"带人能力"},{"key":"C","text":"加班时长"},{"key":"D","text":"个人绩效"}], "B", "综合", 1, 5),
    ("judge", "跨岗位轮岗有助于培养综合能力。", None, "true", "综合", 1, 5),
    ("single", "制定职业规划的第一步是？", [{"key":"A","text":"自我认知"},{"key":"B","text":"投简历"},{"key":"C","text":"考证"},{"key":"D","text":"跳槽"}], "A", "综合", 1, 10),
    ("multi", "以下属于软技能的有？", [{"key":"A","text":"沟通"},{"key":"B","text":"协作"},{"key":"C","text":"编程"},{"key":"D","text":"批判性思维"}], "A,B,D", "综合", 2, 10),
    ("single", "面对多项任务同时到期，首先应？", [{"key":"A","text":"按紧急重要排序"},{"key":"B","text":"随机处理"},{"key":"C","text":"全部自己做"},{"key":"D","text":"拖延"}], "A", "综合", 1, 5),
    ("judge", "主动复盘是快速成长的常见方法。", None, "true", "综合", 1, 5),
]

# ---------- 50 条组卷 ----------
PAPERS = [
    ("月度技术考核-2026-01", 60, 100, "manual"),
    ("月度技术考核-2026-02", 60, 100, "manual"),
    ("月度技术考核-2026-03", 60, 100, "auto"),
    ("月度技术考核-2026-04", 60, 100, "auto"),
    ("月度技术考核-2026-05", 60, 100, "manual"),
    ("季度综合测评-Q1", 90, 120, "auto"),
    ("季度综合测评-Q2", 90, 120, "auto"),
    ("新员工入职测评-A", 45, 80, "manual"),
    ("新员工入职测评-B", 45, 80, "manual"),
    ("新员工入职测评-C", 45, 80, "auto"),
    ("Python 后端专项", 75, 100, "manual"),
    ("Java 开发专项", 75, 100, "auto"),
    ("前端工程师测评", 60, 90, "manual"),
    ("数据库基础考核", 40, 60, "manual"),
    ("SQL 查询专项", 30, 50, "auto"),
    ("Redis 实战测评", 35, 60, "auto"),
    ("Docker 容器化测评", 45, 80, "manual"),
    ("Git 版本控制测试", 30, 50, "manual"),
    ("微服务架构认知", 60, 100, "auto"),
    ("敏捷开发知识考试", 50, 80, "manual"),
    ("项目管理基础认证", 90, 100, "auto"),
    ("PMP 模拟测试-卷一", 120, 150, "auto"),
    ("PMP 模拟测试-卷二", 120, 150, "auto"),
    ("沟通协作能力评估", 40, 60, "manual"),
    ("向上汇报技巧测评", 30, 50, "manual"),
    ("跨部门协同测试", 45, 70, "auto"),
    ("逻辑思维测试-基础", 30, 50, "manual"),
    ("逻辑思维测试-进阶", 45, 70, "auto"),
    ("推理能力评估", 35, 60, "manual"),
    ("领导力测评", 60, 90, "auto"),
    ("管理能力综合评估", 90, 100, "auto"),
    ("团队管理实战测试", 60, 80, "manual"),
    ("英语水平摸底-基础", 40, 50, "manual"),
    ("英语水平摸底-进阶", 50, 60, "auto"),
    ("英语商务场景测评", 45, 55, "auto"),
    ("数据分析基础考核", 60, 100, "manual"),
    ("AI 认知测评", 40, 60, "auto"),
    ("机器学习基础测试", 60, 100, "manual"),
    ("深度学习入门测评", 75, 120, "auto"),
    ("产品思维测试", 50, 80, "manual"),
    ("产品经理认证模拟", 90, 100, "auto"),
    ("运营能力评估", 45, 70, "manual"),
    ("销售能力测评", 40, 60, "manual"),
    ("客户服务技巧测试", 35, 50, "auto"),
    ("职业素养测评", 30, 50, "manual"),
    ("抗压能力评估", 25, 40, "auto"),
    ("时间管理测试", 30, 50, "manual"),
    ("面试官技能测评", 45, 70, "auto"),
    ("年度综合能力测评", 120, 150, "auto"),
    ("晋升答辩模拟卷", 60, 100, "manual"),
]


def main() -> None:
    db = SessionLocal()
    try:
        # 1) 插入题目
        qids = []
        for (qtype, content, options, answer, dim, diff, score) in NEW_QUESTIONS:
            q = Question(
                bank_id=1, type=qtype, content=content,
                options=__import__("json").dumps(options, ensure_ascii=False) if options else None,
                answer=answer, dimension=dim, difficulty=diff, score=score, status=1,
            )
            db.add(q)
            db.flush()
            qids.append(q.id)
        print(f"[OK] 已插入 {len(qids)} 道新题目")

        # 2) 插入 50 条试卷（随机抽题组卷）
        base = datetime(2026, 8, 1)
        paper_count = 0
        for idx, (title, duration, total, method) in enumerate(PAPERS):
            paper = Paper(
                title=title, description=f"{method}组卷 · 演示数据", difficulty=random.randint(1, 4),
                total_score=total, duration_min=duration,
                gen_method=method, status=1 if idx % 5 != 4 else 0,  # 每 5 条停用 1 条
                created_by=1,
                created_at=base - timedelta(days=idx * 3 % 60),
            )
            db.add(paper)
            db.flush()
            # 随机抽 5-10 道题
            picked = random.sample(qids, k=min(random.randint(5, 10), len(qids)))
            for sort_i, qid in enumerate(picked):
                db.add(PaperQuestion(paper_id=paper.id, question_id=qid, sort=sort_i))
            paper_count += 1
        db.commit()
        print(f"[OK] 已插入 {paper_count} 条组卷，共关联 {len(qids)} 道题")
    except Exception as e:
        db.rollback()
        print(f"[FAIL] {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
