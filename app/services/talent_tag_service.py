"""人才标签服务（批次2.1 → 合并后适配 tal_tag）。

2026-09-01 合并适配（hq+）：
- 标签统一用袁文武 ``tal_tag``（name/category/is_builtin）+ ``tal_talent_tag``
- ``TalentAutoTagger.auto_tag`` 规则版自动打标签：按 tal_tag.name 关键字匹配
- 保留原入口（resume_upload_service 调用），返回 tag_id 列表

仅本模块新增。
"""
# hq新增内容 - 人才档案批次2.1 + 合并
from sqlalchemy.orm import Session

from app.models.talent import Talent, TalentTag


class TalentAutoTagger:
    """规则版自动打标签：基于现有 tal_tag 名称与人才字段做关键字匹配。

    命中条件（tal_tag.name 子串匹配，命中即返回该 tag id）：
    - 年限 >= 10 → 「10年以上经验」；>= 5 → 「5年以上经验」
    - current_title 含「架构」 → 「架构师」；含「经理/总监」 → 「管理岗」
    - highest_education 硕士/博士 → 「高学历」
    - summary 含「数字化转型」 → 「数字化转型」；AI 相关 → 「人工智能」
    """

    @staticmethod
    def auto_tag(db: Session, talent: Talent) -> list[int]:
        """对单个人才计算应挂的标签 tag_id 列表（去重）。返回 tag id 集合。"""
        all_tags = db.query(TalentTag).all()
        name2id = {t.name: t.id for t in all_tags}
        hits: list[int] = []

        def _hit(names: list[str]) -> None:
            for n in names:
                tid = name2id.get(n)
                if tid:
                    hits.append(tid)

        exp = talent.years_experience or 0
        if exp >= 10:
            _hit(["10年以上经验"])
        elif exp >= 5:
            _hit(["5年以上经验"])

        title = (talent.current_title or "").lower()
        if any(k in title for k in ("架构师", "架构")):
            _hit(["架构师"])
        if any(k in title for k in ("总监", "经理", "manager")):
            _hit(["管理岗"])

        edu = (talent.highest_education or "")
        if edu in ("硕士", "博士"):
            _hit(["高学历", "高学历（硕博）"])

        summary = (talent.summary or "") + (talent.resume_text or "")
        if "数字化转型" in summary:
            _hit(["数字化转型"])
        if any(k in summary for k in ("人工智能", "大模型", "AI", " llm", "LLM")):
            _hit(["人工智能", "AI工程师", "AI 工程师"])

        # 去重保持顺序
        seen: set[int] = set()
        return [x for x in hits if not (x in seen or seen.add(x))]
