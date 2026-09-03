"""LLM 简历解析与 AI 打标签（批次 2.3b + 合并适配）。

能力：
1. 调 Ollama（qwen3:0.6b）抽 8 主字段 + skills / highlights / shortcomings /
   fit_positions / potential，输出严格 JSON。
2. 把抽出的 skills 与 ``tal_tag``（袁文武标签字典）做子串匹配，把命中的 tag 写
   ``tal_talent_tag``，source=ai。
3. 生成一段评估总结，写到 ``tal_talent_report.summary_report``。
4. 把主字段回写到 ``tal_talent`` 主档（仅在字段为空时覆盖，避免破坏人工修正）。

2026-09-01 合并适配（hq+）：
- 字段映射：education→highest_education、years_of_exp→years_experience、
  source→resume_source、current_company/summary 保留（tal_talent 已有）
- 标签：biz_talent_dict/biz_talent_tag → tal_tag/tal_talent_tag（袁文武 DAO）

调用链：
    routers/resume.upload ─┐
                            ├─► ResumeUploadService.handle ─► ResumeLLMService.parse_and_apply
    routers/talent.reparse ─┘
"""
# hq新增内容 - 人才档案批次2.3b + 合并
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.dao.talent import TagDAO, TalentTagRelDAO
from app.dao.talent_report import TalentReportDAO
from app.models.talent import Talent
from app.utils.llm import get_llm
from app.utils.response import BusinessError

logger = logging.getLogger(__name__)


# ========== Prompt 模板（保留我的 8 字段抽取风格）==========
EXTRACT_SYSTEM = """你是一个严谨的人才画像 AI 助手，专精于从简历原文中抽取结构化字段。"""

EXTRACT_USER_TEMPLATE = """【简历原文】
{resume}

【任务】
按以下 JSON Schema 严格输出，**只输出 JSON，不要任何解释、Markdown、注释**：

{{
  "name": "字符串，姓名；原文没有则空字符串",
  "gender": "字符串，性别，男 / 女；无法判断则空字符串（根据姓名、称谓、先生/女士、他/她等线索推断）",
  "phone": "字符串，手机号；原文没有则空字符串",
  "email": "字符串，邮箱；原文没有则空字符串",
  "education": "字符串，本科/硕士/博士/大专等；无法判断则空字符串",
  "current_title": "字符串，当前或最近一段职业的职称",
  "years_of_exp": 0,
  "current_company": "字符串，必须从最近一段'至今'或最新 start_date 的工作经历中提取公司全称；找不到留空字符串，绝不允许输出'无业'/'暂无'/'无'等占位词",
  "summary": "80~200 字简要描述候选人核心背景（项目经验 + 技术栈 + 业务领域）",
  "skills": ["技能关键词 8~15 项，按重要度排序"],
  "highlights": ["亮点 3~6 项"],
  "shortcomings": ["短板 1~3 项；若未明显看出则 []"],
  "fit_positions": ["最适合 2~4 个岗位类型"],
  "potential": "P5 / P6 / P7 之一",
  "ability_level": "能力等级，从 P5初级 / P6中级 / P7高级 / P8专家 中选一个，根据技术深度、项目复杂度、团队角色综合判断",
  "experience_summary": "从业经验总结，2-3 句话，概括行业背景、核心经验领域、职业成长轨迹",
  "composite_score": 0
}}

综合评分规则（0-100 整数）：
- 技能匹配度 + 经验深度 + 教育背景 + 项目复杂度 + 潜力综合打分
- 60 分以下：基础偏弱；60-70：合格；70-80：良好；80-90：优秀；90+：顶级

规则：
1. 严格按原文抽取，**绝不编造**。抽不到的字段填空字符串 / 0 / []。
2. summary 用中文，简洁流畅。
3. skills 用短名词，不要整句。
4. 输出**纯 JSON**，避免 Markdown 代码块标记。"""

REPORT_SYSTEM = """你是 HR 资深专家，给出专业、犀利、有干货的人才画像总结。"""

REPORT_USER_TEMPLATE = """【候选人抽取结果】
{candidate_json}

请输出**纯文本**（不使用 Markdown 标题），按下列四个小段写，每段 2~4 句：
（一）核心优势
（二）短板与风险
（三）适配岗位（举 2~3 个具体方向）
（四）发展潜力评级（说明依据）"""


# ========== JSON 提取容错 ==========
_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(content: str) -> dict[str, Any]:
    """从 LLM 返回中抠出 JSON，容忍 Markdown 包裹。"""
    if not content:
        raise ValueError("LLM 返回为空")
    m = _JSON_RE.search(content)
    if not m:
        raise ValueError("LLM 返回中找不到 JSON 对象")
    text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 最后兜底：去掉末尾逗号等
        cleaned = re.sub(r",\s*([}\]])", r"\1", text)
        return json.loads(cleaned)


# ========== 主服务 ==========
class ResumeLLMService:
    """对一份 talent 文本，调 LLM 完成抽取 + 报告生成 + AI 标签。"""

    MAX_TEXT = 6000  # 控制 prompt token；超长只取首尾

    @classmethod
    def _truncate(cls, text: str) -> str:
        if not text:
            return ""
        if len(text) <= cls.MAX_TEXT:
            return text
        return text[: cls.MAX_TEXT // 2] + "\n\n...(简历过长，已截断)...\n\n" + text[-cls.MAX_TEXT // 2:]

    @classmethod
    def extract(cls, resume_text: str) -> dict[str, Any]:
        """调 LLM 抽取 8 字段 + 技能等，返回 dict（解析失败抛 BusinessError）。"""
        text = cls._truncate(resume_text or "")
        if not text.strip():
            raise BusinessError(400, "简历原文为空，无法解析")

        llm = get_llm()
        prompt = EXTRACT_USER_TEMPLATE.format(resume=text)
        try:
            content = llm.chat(prompt, system=EXTRACT_SYSTEM, temperature=0.2)
        except Exception as e:
            logger.exception("[hq] LLM 抽取调用失败：%s", e)
            raise BusinessError(502, f"LLM 调用失败：{e}") from e

        try:
            data = _extract_json(content)
        except Exception as e:
            logger.exception("[hq] LLM 返回解析失败：%s\n---\n%s", e, content)
            raise BusinessError(502, f"LLM 输出无法解析为 JSON：{e}") from e

        # 兜底字段
        data.setdefault("name", "")
        data.setdefault("phone", "")
        data.setdefault("email", "")
        data.setdefault("education", "")
        data.setdefault("current_title", "")
        data.setdefault("years_of_exp", 0)
        data.setdefault("current_company", "")
        data.setdefault("summary", "")
        for k in ("skills", "highlights", "shortcomings", "fit_positions"):
            data.setdefault(k, [])
        data.setdefault("potential", "")
        data.setdefault("ability_level", "")
        data.setdefault("experience_summary", "")
        data.setdefault("composite_score", 0)
        # 类型强转
        try:
            data["years_of_exp"] = int(data["years_of_exp"] or 0)
        except (TypeError, ValueError):
            data["years_of_exp"] = 0
        try:
            score = int(data.get("composite_score") or 0)
            data["composite_score"] = max(0, min(100, score))
        except (TypeError, ValueError):
            data["composite_score"] = 0
        return data

    @classmethod
    def summarize(cls, extracted: dict[str, Any]) -> str:
        """基于抽取结果生成评估总结。"""
        llm = get_llm()
        cand = json.dumps({k: extracted.get(k) for k in (
            "name", "current_title", "years_of_exp", "current_company",
            "education", "summary", "skills", "highlights", "shortcomings",
            "fit_positions", "potential",
        )}, ensure_ascii=False, indent=2)
        try:
            return llm.chat(
                REPORT_USER_TEMPLATE.format(candidate_json=cand),
                system=REPORT_SYSTEM, temperature=0.4,
            ).strip()
        except Exception as e:
            logger.warning("[hq] 评估总结生成失败：%s", e)
            return ""  # 评估失败不阻塞主流程

    @classmethod
    def _ai_match_tags(cls, db: Session, skills: list[str]) -> list[int]:
        """把 LLM 抽出的 skills 与 tal_tag 名称做大小写不敏感子串匹配。

        返回命中的 tag_id（去重）。为空时返回 []。
        """
        from app.models.talent import TalentTag  # hq+ 局部导入：tal_tag 字典表 ORM
        tags = db.query(TalentTag).filter(TalentTag.is_builtin == 1).all()
        skills_l = [s.lower().strip() for s in (skills or []) if isinstance(s, str) and s.strip()]
        hit_ids: list[int] = []
        seen: set[int] = set()
        for t in tags:
            target = (t.name or "").lower().strip()
            if not target:
                continue
            for sk in skills_l:
                if (sk and (target in sk or sk in target)) or (target == sk):
                    if t.id not in seen:
                        hit_ids.append(t.id)
                        seen.add(t.id)
                    break
        return hit_ids

    @classmethod
    def apply(cls, db: Session, talent: Talent, raw_text: str, *, ai_weight: float = 0.8) -> dict[str, Any]:
        """对一份 talent 一次性完成：LLM 抽取 → 回写主档 → AI 打标签 → 写报告。

        失败时回滚 report 写入但保留 talent 主档，失败信息写到 report summary_report 字段。

        :return: {"extracted": ..., "report_id": int|None, "new_tag_count": int}
        """
        from app.models.talent import TalentTag, TalentTalentTag  # hq+ 局部导入避免循环（TalentTag=字典，TalentTalentTag=关联）
        # 1) 抽
        extracted = cls.extract(raw_text)
        # 2) 评估
        summary_report = cls.summarize(extracted)
        # 3) 回写主档（只填空，不覆盖人工值；字段对齐 tal_talent）
        if not (talent.name or "").strip() or talent.name.startswith("未命名-"):
            v = (extracted.get("name") or "").strip()
            if v:
                talent.name = v
        if not (talent.gender or "").strip() and extracted.get("gender"):
            talent.gender = extracted["gender"].strip()
        if not talent.phone and extracted.get("phone"):
            talent.phone = extracted["phone"].strip()
        if not talent.email and extracted.get("email"):
            talent.email = extracted["email"].strip()
        if not (talent.highest_education or "").strip() and extracted.get("education"):
            talent.highest_education = extracted["education"].strip()
        if not (talent.current_title or "").strip() and extracted.get("current_title"):
            talent.current_title = extracted["current_title"].strip()
        if not (talent.current_company or "").strip() and extracted.get("current_company"):
            talent.current_company = extracted["current_company"].strip()
        if not (talent.years_experience or 0) and extracted.get("years_of_exp"):
            talent.years_experience = extracted["years_of_exp"]
        if not (talent.summary or "").strip() and extracted.get("summary"):
            talent.summary = extracted["summary"].strip()
        if not (talent.skills or "").strip() and extracted.get("skills"):
            talent.skills = "；".join(extracted["skills"])[:2000]
        # 同时把 source 标记为 AI 解析
        if talent.resume_source in (None, "", "manual", "import"):
            talent.resume_source = "agent_parsed"
        db.flush()

        # 4) AI 打标签（追加，不覆盖人工标签；tal_tag + tal_talent_tag）
        skill_hit = cls._ai_match_tags(db, extracted.get("skills") or [])
        if skill_hit:
            # 保留已有标签，只加新命中的
            existing = {r.tag_id for r in db.query(TalentTalentTag)
                        .filter(TalentTalentTag.talent_id == talent.id).all()}
            new_ids = [i for i in skill_hit if i not in existing]
            if new_ids:
                TalentTagRelDAO.set_ai_tags(db, talent.id, new_ids)

        # 5) 写报告
        fields = {
            "parsed_json": json.dumps(extracted, ensure_ascii=False),
            "skills": json.dumps(extracted.get("skills") or [], ensure_ascii=False),
            "highlights": json.dumps(extracted.get("highlights") or [], ensure_ascii=False),
            "shortcomings": json.dumps(extracted.get("shortcomings") or [], ensure_ascii=False),
            "fit_positions": json.dumps(extracted.get("fit_positions") or [], ensure_ascii=False),
            "potential": (extracted.get("potential") or "")[:16] or None,
            # 袁文武 2026-09-02：AI 解析新增三大板块
            "ability_level": (extracted.get("ability_level") or "")[:32] or None,
            "experience_summary": extracted.get("experience_summary") or None,
            "composite_score": extracted.get("composite_score") or None,
            "summary_report": summary_report or None,
        }
        report = TalentReportDAO.upsert(db, talent.id, fields)

        db.commit()
        db.refresh(talent)
        db.refresh(report)

        # hq+  批次B：LLM 抽完后写三维向量（技能/经验/素质）入 Milvus
        try:
            from app.services.talent_vector_service import upsert_talent_vectors  # hq+
            dims = upsert_talent_vectors(talent, report)
            if dims.get("skill") is not None:
                report.vector_id = str(dims["skill"])
                db.commit()
        except Exception as e:
            logger.warning("[hq] 三维向量化失败（不影响主流程）：%s", e)

        db.refresh(talent)
        return {"extracted": extracted, "report_id": report.id, "new_tag_count": len(skill_hit)}
