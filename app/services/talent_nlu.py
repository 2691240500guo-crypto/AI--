#袁文武新增2026-09-03 语义搜索v2 NLU解析器
"""
语义搜索 NLU 查询解析器（LLM 模式 + 规则降级双轨制）

将自然语言查询解析为结构化搜索意图（SearchIntent），支持：
- 年限范围（3年以上、5年左右、1-3年）
- 学历要求（本科以上、硕士、博士）
- 能力等级（骨干、高级、专家、初级）
- 技能关键词（Python、AI、数字化转型...）
- 岗位方向（产品经理、前端工程师...）

降级链路：
  LLM 解析 → 失败/超时时 → 规则解析（正则+关键词词典）→ 失败 → 纯关键词
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------- 数据结构 ----------------

@dataclass
class SearchIntent:
    """结构化搜索意图。"""
    raw_query: str
    years_min: Optional[int] = None
    years_max: Optional[int] = None
    education: Optional[str] = None
    education_min: Optional[str] = None
    level: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    position_keywords: list[str] = field(default_factory=list)
    industry_keywords: list[str] = field(default_factory=list)
    parse_mode: str = "fallback"
    parsed_conditions: list[str] = field(default_factory=list)

    def has_structured_filter(self) -> bool:
        return (
            self.years_min is not None
            or self.years_max is not None
            or self.education is not None
            or self.education_min is not None
            or self.level is not None
        )

    def has_keywords(self) -> bool:
        return bool(self.keywords or self.position_keywords or self.industry_keywords)

    def all_keywords(self) -> list[str]:
        seen = set()
        out = []
        for kw in self.keywords + self.position_keywords + self.industry_keywords:
            if kw and kw not in seen:
                seen.add(kw)
                out.append(kw)
        return out


# ---------------- 词典 ----------------

_LEVEL_KEYWORDS = {
    "初级": "初级", "入门": "初级", "应届生": "初级",
    "中级": "中级",
    "高级": "高级", "资深": "高级",
    "骨干": "骨干", "骨干人才": "骨干", "技术骨干": "骨干",
    "专家": "专家", "技术专家": "专家", "领域专家": "专家",
    "架构师": "架构师", "技术架构师": "架构师",
    "负责人": "负责人", "模块负责人": "负责人",
    "管理者": "管理者", "主管": "管理者",
    "总监": "技术总监", "技术总监": "技术总监",
}

_EDU_KEYWORDS = {
    "大专": "大专", "专科": "大专", "高职": "大专",
    "本科": "本科", "学士": "本科", "本科学历": "本科",
    "硕士": "硕士", "研究生": "硕士", "硕士研究生": "硕士",
    "博士": "博士", "博士生": "博士", "博士研究生": "博士",
    "博士后": "博士",
}

_STOP_WORDS = {
    "的", "了", "是", "在", "有", "和", "与", "及", "等", "也", "都", "就",
    "要", "找", "查找", "搜索", "查询", "筛选", "找出", "看看", "哪些", "谁",
    "人才", "员工", "人员", "候选人", "候选", "简历", "档案",
    "请问", "帮我", "给我", "我想", "想要", "需要", "可以", "能",
    "吗", "呢", "啊", "吧", "呀", "哦",
    "有哪些", "有多少", "有什么", "哪些是", "谁是",
    "工作经验", "经验", "从业经验", "工作年限", "年限",
    "以上", "以下", "左右", "大约", "大概",
    "擅长", "精通", "熟练", "熟悉", "掌握", "了解",
    "从事", "做过", "负责", "担任", "任职",
    "相关", "方面", "领域", "方向", "类型",
    "项目", "项目经验", "行业", "公司", "企业",
}

_SKILL_DICT = [
    "人工智能", "AI", "AIGC", "大模型", "大语言模型", "LLM",
    "机器学习", "深度学习", "NLP", "自然语言处理", "计算机视觉", "CV",
    "数据分析", "数据挖掘", "数据建模", "数据治理", "数据中台",
    "ETL", "数据仓库", "数仓", "BI", "商业智能",
    "数字化转型", "数字化", "智能化",
    "Python", "Java", "Go", "Golang", "C++", "C#", "JavaScript", "JS",
    "TypeScript", "TS", "Rust", "PHP", "Ruby", "Swift", "Kotlin",
    "SQL", "MySQL", "PostgreSQL", "PgSQL", "Oracle", "MongoDB", "Redis",
    "Docker", "Kubernetes", "K8s", "DevOps", "CI/CD",
    "FastAPI", "Spring Boot", "Spring", "Django", "Flask", "Vue", "React",
    "前端", "后端", "全栈", "算法", "测试", "运维", "架构",
    "微服务", "分布式", "高并发", "性能优化",
    "产品经理", "产品设计", "需求分析", "交互设计", "UI设计", "UX",
    "项目管理", "项目经理", "PMP", "敏捷开发", "Scrum",
    "人力资源", "HR", "招聘", "薪酬", "绩效", "培训",
    "财务", "会计", "市场营销", "市场", "销售", "运营", "产品运营",
    "金融", "银行", "保险", "证券",
    "制造业", "工业", "汽车", "电子", "半导体",
    "互联网", "电商", "教育", "医疗",
    "TensorFlow", "PyTorch", "Pandas", "NumPy",
    "大数据", "Hadoop", "Spark", "Flink", "Kafka",
    "云原生", "云计算", "AWS", "阿里云", "腾讯云",
    "信息安全", "网络安全", "渗透测试", "等保",
    "RAG", "LangChain", "LangGraph", "Agent", "智能体",
    "Prompt", "提示词", "Fine-tuning", "微调",
]

_POSITION_DICT = [
    "产品经理", "项目经理", "产品总监", "技术总监",
    "前端工程师", "后端工程师", "全栈工程师", "算法工程师", "数据工程师",
    "测试工程师", "运维工程师", "架构师", "技术专家",
    "数据分析师", "数据科学家", "BI工程师",
    "UI设计师", "UX设计师", "交互设计师", "产品设计师",
    "HRBP", "招聘专员", "培训专员", "人事专员",
    "财务专员", "会计", "出纳",
    "市场经理", "销售经理", "运营经理",
    "客户经理", "BD经理", "商务经理",
]


# ---------------- 规则解析器 ----------------

def parse_by_rules(query: str) -> SearchIntent:
    """用规则（正则+关键词词典）解析查询，零 AI 依赖。"""
    intent = SearchIntent(raw_query=query, parse_mode="rule")
    text = query.strip()

    years_min, years_max, years_text = _extract_years(text)
    intent.years_min = years_min
    intent.years_max = years_max
    if years_text:
        intent.parsed_conditions.append(years_text)

    edu, edu_min, edu_text = _extract_education(text)
    intent.education = edu
    intent.education_min = edu_min
    if edu_text:
        intent.parsed_conditions.append(edu_text)

    level, level_text = _extract_level(text)
    intent.level = level
    if level_text:
        intent.parsed_conditions.append(level_text)

    skills = _extract_keywords(text, _SKILL_DICT)
    positions = _extract_keywords(text, _POSITION_DICT)

    pos_set = set(positions)
    unique_skills = []
    seen_kw = set()
    for kw in skills:
        if kw in pos_set:
            continue
        kw_lower = kw.lower()
        if kw_lower in seen_kw:
            continue
        if kw in _STOP_WORDS or kw_lower in {"经验", "以上", "以下", "工作", "以上经验", "以下经验"}:
            continue
        if kw.isdigit() or len(kw) < 2:
            continue
        seen_kw.add(kw_lower)
        unique_skills.append(kw)
    intent.keywords = unique_skills

    unique_pos = []
    seen_pos = set()
    for kw in positions:
        if kw.lower() not in seen_pos:
            seen_pos.add(kw.lower())
            unique_pos.append(kw)
    intent.position_keywords = unique_pos

    if len(intent.all_keywords()) < 2:
        extra = _extract_extra_keywords(text)
        for kw in extra:
            if kw not in pos_set and kw not in set(intent.keywords):
                intent.keywords.append(kw)

    if intent.keywords:
        intent.parsed_conditions.append(f"技能关键词：{'、'.join(intent.keywords[:5])}")
    if intent.position_keywords:
        intent.parsed_conditions.append(f"岗位方向：{'、'.join(intent.position_keywords)}")

    if not intent.has_structured_filter() and not intent.has_keywords():
        intent.parse_mode = "fallback"
        intent.keywords = [text]

    return intent


def _extract_years(text: str) -> tuple[Optional[int], Optional[int], str]:
    m = re.search(r"(\d+)\s*年\s*(以上|以上经验|多|及以上|\+|or above)", text)
    if m:
        y = int(m.group(1))
        return y, None, f"{y}年以上经验"
    m = re.search(r"(\d+)\s*年\s*(以下|以内|以下经验)", text)
    if m:
        y = int(m.group(1))
        return None, y, f"{y}年以下经验"
    m = re.search(r"(\d+)\s*[\-~到至]\s*(\d+)\s*年", text)
    if m:
        y1 = int(m.group(1))
        y2 = int(m.group(2))
        return min(y1, y2), max(y1, y2), f"{min(y1,y2)}-{max(y1,y2)}年经验"
    m = re.search(r"(\d+)\s*年(工作|从业|项目)?经验", text)
    if m:
        y = int(m.group(1))
        return y, y, f"{y}年经验"
    if re.search(r"应届|刚毕业|毕业生", text):
        return 0, 1, "应届/0-1年"
    return None, None, ""


def _extract_education(text: str) -> tuple[Optional[str], Optional[str], str]:
    m = re.search(r"(大专|本科|硕士|博士)\s*(及以上|以上|学历以上|或以上)", text)
    if m:
        edu = _EDU_KEYWORDS.get(m.group(1), m.group(1))
        return None, edu, f"{edu}及以上学历"
    for kw, std in _EDU_KEYWORDS.items():
        if kw in text:
            return std, None, f"{std}学历"
    return None, None, ""


def _extract_level(text: str) -> tuple[Optional[str], str]:
    text_clean = text
    skip_phrases = ["产品经理", "项目经理", "客户经理", "BD经理", "商务经理",
                    "销售经理", "市场经理", "运营经理", "部门经理"]
    for phrase in skip_phrases:
        text_clean = text_clean.replace(phrase, "")
    for kw, std in _LEVEL_KEYWORDS.items():
        if kw in text_clean:
            return std, f"{std}等级"
    return None, ""


def _extract_keywords(text: str, dictionary: list[str]) -> list[str]:
    found = []
    for kw in dictionary:
        if kw.lower() in text.lower():
            found.append(kw)
    found.sort(key=len, reverse=True)
    return found


def _extract_extra_keywords(text: str) -> list[str]:
    cleaned = re.sub(r"[，。、；：？！,.\?;:\!\(\)（）\[\]【】\"'`]", " ", text)
    cleaned = re.sub(r"\d+\s*年", " ", cleaned)
    words = [w.strip() for w in cleaned.split() if w.strip()]
    result = []
    for w in words:
        if w in _STOP_WORDS or len(w) < 2:
            continue
        result.append(w)
    return result[:5]


# ---------------- LLM 解析器 ----------------

def parse_by_llm(query: str) -> Optional[SearchIntent]:
    """用 LLM 解析查询为结构化意图。失败时返回 None。"""
    try:
        from app.utils.llm import get_llm
        llm = get_llm()
    except Exception:
        return None

    prompt = f"""你是人才搜索查询解析器。请将用户的自然语言查询解析为 JSON 格式的搜索条件。

只输出 JSON，不要输出其他文字。JSON 字段说明：
{{
  "years_min": 数字或null，工作年限最小值（年），如 "3年以上" → 3
  "years_max": 数字或null，工作年限最大值（年）
  "education": "大专/本科/硕士/博士" 或 null，精确学历
  "education_min": "大专/本科/硕士/博士" 或 null，最低学历
  "level": "初级/中级/高级/骨干/专家/架构师/负责人/管理者/技术总监" 或 null
  "keywords": ["技能关键词1", "技能关键词2"]
  "position_keywords": ["岗位名1"]
  "industry_keywords": ["行业名1"]
  "parsed_conditions": ["条件描述1", "条件描述2"]
}}

查询："{query}"

JSON:"""

    try:
        response = llm.chat(prompt, system="你是精准的查询解析器，只输出合法 JSON。", temperature=0.1)
        json_str = _extract_json(response)
        if not json_str:
            return None
        import json as _json
        data = _json.loads(json_str)

        intent = SearchIntent(
            raw_query=query,
            years_min=data.get("years_min"),
            years_max=data.get("years_max"),
            education=data.get("education"),
            education_min=data.get("education_min"),
            level=data.get("level"),
            keywords=[k for k in data.get("keywords", []) if k and isinstance(k, str)],
            position_keywords=[k for k in data.get("position_keywords", []) if k and isinstance(k, str)],
            industry_keywords=[k for k in data.get("industry_keywords", []) if k and isinstance(k, str)],
            parse_mode="llm",
            parsed_conditions=[c for c in data.get("parsed_conditions", []) if c and isinstance(c, str)],
        )

        if not intent.has_structured_filter() and not intent.has_keywords():
            return None
        if not intent.parsed_conditions:
            intent.parsed_conditions = _generate_condition_texts(intent)
        return intent
    except Exception:
        return None


def _extract_json(text: str) -> Optional[str]:
    if not text:
        return None
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return None


def _generate_condition_texts(intent: SearchIntent) -> list[str]:
    texts = []
    if intent.years_min is not None and intent.years_max is not None:
        if intent.years_min == intent.years_max:
            texts.append(f"{intent.years_min}年经验")
        else:
            texts.append(f"{intent.years_min}-{intent.years_max}年经验")
    elif intent.years_min is not None:
        texts.append(f"{intent.years_min}年以上经验")
    elif intent.years_max is not None:
        texts.append(f"{intent.years_max}年以下经验")
    if intent.education_min:
        texts.append(f"{intent.education_min}及以上学历")
    elif intent.education:
        texts.append(f"{intent.education}学历")
    if intent.level:
        texts.append(f"{intent.level}等级")
    if intent.keywords:
        texts.append(f"关键词：{'、'.join(intent.keywords[:5])}")
    if intent.position_keywords:
        texts.append(f"岗位：{'、'.join(intent.position_keywords[:3])}")
    return texts


# ---------------- 统一入口 ----------------

def parse_query(query: str, prefer_llm: bool = True) -> SearchIntent:
    """解析自然语言查询，自动选择 LLM 或规则模式。"""
    if not query or not query.strip():
        return SearchIntent(raw_query=query, parse_mode="fallback")
    if prefer_llm:
        intent = parse_by_llm(query)
        if intent is not None:
            return intent
    intent = parse_by_rules(query)
    return intent
