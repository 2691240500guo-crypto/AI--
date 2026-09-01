#袁文武新增2026-08-31 17:10:00开始
"""简历解析工具（需求① 全格式简历智能解析）。

能力：
  - 文本提取：PDF（pdfminer.six / PyPDF2）、Word（python-docx）、图片（OCR 引擎）
  - AI 结构化：调用 Ollama 大模型，将自由文本清洗、纠错、标准化为结构化字段
文本提取与 LLM 均为惰性导入，对应依赖未安装时抛出清晰的业务异常，不影响其它模块运行。
"""
from __future__ import annotations

import io
import json
import re

from app.utils.llm import get_llm
from app.utils.response import BusinessError

_STRUCTURE_PROMPT = """你是一名资深 HR 数据标注专家。请将下面这段简历/人才介绍文本，解析为标准 JSON。
要求：
1. 自动清洗、纠错、补全缺失字段（无法确定的字段填 null）；
2. 字段包括：name, gender, phone, email, highest_education, major, current_title,
   years_experience(整数), salary_expectation, skills(用分号分隔的字符串),
   work_experience, project_experience, honors,
   educations:[{school,degree,major,start_year,end_year}],
   works:[{company,title,start_date,end_date,description}],
   projects:[{name,role,description}]；
3. 只输出 JSON，不要任何解释与 markdown 代码块标记。
简历文本：
"""


def extract_text(filename: str, content: bytes) -> str:
    """按扩展名分派提取器，返回纯文本。"""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    if name.endswith((".docx", ".doc")):
        return _extract_docx(content)
    if name.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff")):
        return _extract_image(content)
    # 兜底：当作纯文本
    try:
        return content.decode("utf-8", "ignore")
    except Exception:
        return ""


def _extract_pdf(content: bytes) -> str:
    # 优先 pdfminer.six，回退 PyPDF2
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract
        return pdfminer_extract(io.BytesIO(content)) or ""
    except Exception:
        pass
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        raise BusinessError(500, f"PDF 解析失败，请确认已安装 pdfminer.six 或 PyPDF2：{e}")


def _extract_docx(content: bytes) -> str:
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs if p.text]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts)
    except Exception as e:
        raise BusinessError(500, f"Word 解析失败，请确认已安装 python-docx：{e}")


def _extract_image(content: bytes) -> str:
    """图片简历：优先 OCR 引擎识别文字；无 OCR 时给出明确提示。"""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(io.BytesIO(content)), lang="chi_sim+eng")
        if text and text.strip():
            return text
    except Exception:
        pass
    try:
        import easyocr
        reader = easyocr.Reader(["ch_sim", "en"], verbose=False)
        result = reader.readtext(content, detail=0)
        text = "\n".join(result)
        if text.strip():
            return text
    except Exception:
        pass
    raise BusinessError(
        500,
        "图片简历需 OCR 引擎：请安装 pytesseract+ Tesseract（中文包）或 easyocr；"
        "或改用 PDF/Word 版本导入。",
    )


#袁文武新增2026-09-01 11:10:00开始 - 正则降级解析，LLM不可用时自动回退
def structurize(text: str) -> dict:
    """调用大模型将简历文本结构化为 dict（需求① 解析准确率>=99% 的工程入口）。
    LLM 不可用时自动降级为正则解析，确保功能可用。"""
    if not text or not text.strip():
        raise BusinessError(400, "简历文本为空，无法解析")
    try:
        llm = get_llm()
        raw = llm.chat(_STRUCTURE_PROMPT + text, system="你是严谨的简历结构化助手，只输出 JSON。",
                       temperature=0.1)
        return _parse_json(raw)
    except Exception:
        # LLM 不可用时降级到正则解析
        return _regex_structurize(text)


def _regex_structurize(text: str) -> dict:
    """正则降级解析：从简历文本中提取关键字段（LLM不可用时的兜底方案）。"""
    result = {
        "name": None, "gender": None, "phone": None, "email": None,
        "highest_education": None, "major": None, "current_title": None,
        "years_experience": 0, "salary_expectation": None,
        "skills": None, "work_experience": None, "project_experience": None,
        "honors": None, "educations": [], "works": [], "projects": [],
        "tags": [],
    }
    NL = "\n"

    # 姓名
    m = re.search(r"(?:姓名|名字)[：:]\s*(\S{2,20})", text)
    if m:
        result["name"] = m.group(1)
    else:
        first_line = text.strip().split(NL)[0].strip()
        if 2 <= len(first_line) <= 20 and not re.search(r"[0-9@.]", first_line):
            result["name"] = first_line

    # 性别
    m = re.search(r"性别[：:]\s*(男|女|male|female|M|F)", text, re.I)
    if m:
        g = m.group(1).lower()
        result["gender"] = "男" if g in ("男", "male", "m") else "女"

    # 手机号
    m = re.search(r"(?:手机|电话|tel|phone)[：: ]?\s*(1[3-9]\d{9})", text, re.I)
    if m:
        result["phone"] = m.group(1)
    else:
        m = re.search(r"(1[3-9]\d{9})", text)
        if m:
            result["phone"] = m.group(1)

    # 邮箱
    m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
    if m:
        result["email"] = m.group(0)

    # 学历
    edu_keywords = [
        ("博士", "博士"), ("博士后", "博士后"), ("硕士", "硕士"), ("MBA", "硕士"),
        ("本科", "本科"), ("学士", "本科"), ("大专", "大专"),
        ("专科", "大专"), ("高中", "高中"), ("中专", "中专"),
    ]
    for kw, edu in edu_keywords:
        if kw in text:
            result["highest_education"] = edu
            break
    m = re.search(r"(?:学历|最高学历)[：:]\s*(\S+)", text)
    if m:
        result["highest_education"] = m.group(1)

    # 专业
    m = re.search(r"专业[：:]\s*(\S{2,30})", text)
    if m:
        result["major"] = m.group(1)

    # 职位
    m = re.search(r"(?:职位|岗位|期望职位|求职意向|应聘职位)[：:]\s*(\S{2,30})", text)
    if m:
        result["current_title"] = m.group(1)

    # 工作年限
    m = re.search(r"(\d+)\s*年.*?(?:经验|工作|从业)", text)
    if m:
        result["years_experience"] = int(m.group(1))
    m = re.search(r"(?:工作年限|从业年限|经验)[：:]\s*(\d+)", text)
    if m:
        result["years_experience"] = int(m.group(1))

    # 薪资期望
    m = re.search(r"(?:薪资|薪水|期望薪资|待遇)[：:]\s*(\S+)", text)
    if m:
        result["salary_expectation"] = m.group(1)

    # 技能
    m = re.search(r"(?:技能|专业技能|技术栈|掌握技能)[：:]\s*([^\n]+)", text)
    if m:
        skills_str = m.group(1).strip()
        skills_str = re.sub(r"[，,、/\\|]", ";", skills_str)
        result["skills"] = skills_str

    # 教育经历
    edu_lines = re.findall(
        r"(\d{4})\s*[-~至到]\s*(\d{4}|至今|现在).*?(?:就读于|毕业于|@|在)?\s*(\S{2,30}?学院|\S{2,30}?大学|\S{2,20}学校)",
        text
    )
    for start, end, school in edu_lines:
        result["educations"].append({
            "school": school, "degree": result["highest_education"],
            "major": result["major"],
            "start_year": int(start), "end_year": None if end in ("至今", "现在") else int(end)
        })

    # 工作经历（结构化）
    work_lines = re.findall(
        r"(\d{4}[-年./]\d{0,2}?)\s*[-~至到]\s*(\d{4}[-年./]\d{0,2}?|至今|现在)\s*(\S{2,20})\s*(\S{2,20})",
        text
    )
    for start, end, company, title in work_lines[:5]:
        result["works"].append({
            "company": company, "title": title,
            "start_date": start, "end_date": end, "description": ""
        })

    # 工作经历（文本块）
    if not result["works"]:
        work_section = re.search(
            r"工作经历[：:]?\n([\s\S]*?)(?:\n项目经验|\n教育背景|\n技能|\n荣誉|$)", text
        )
        if work_section:
            result["work_experience"] = work_section.group(1).strip()

    # 项目经验
    proj_section = re.search(
        r"(?:项目经验|项目经历)[：:]?\n([\s\S]*?)(?:\n工作经历|\n教育背景|\n技能|\n荣誉|$)", text
    )
    if proj_section:
        result["project_experience"] = proj_section.group(1).strip()

    # 荣誉/证书
    honor_section = re.search(
        r"(?:荣誉|证书|资质|获奖)[：:]?\n([\s\S]*?)(?:\n工作|\n教育|\n项目|\n技能|$)", text
    )
    if honor_section:
        result["honors"] = honor_section.group(1).strip()

    # 生成技能标签
    if result["skills"]:
        skill_list = [s.strip() for s in result["skills"].split(";") if s.strip()]
        result["tags"] = skill_list[:10]

    # 补充经验标签
    if result["years_experience"] and result["years_experience"] >= 5:
        result["tags"].append("骨干")
    if result["years_experience"] and result["years_experience"] >= 10:
        result["tags"].append("资深")

    return result
#袁文武新增2026-09-01 11:10:00结束


def _parse_json(raw: str) -> dict:
    """从模型输出中稳健解析 JSON（兼容 ```json 代码块 / 前后多余文本）。"""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        raw = raw.strip()
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        raw = raw[start:end + 1]
    try:
        return json.loads(raw)
    except Exception as e:
        raise BusinessError(500, f"简历结构化失败（模型返回非标准 JSON）：{e}")
#袁文武新增2026-08-31 17:10:00结束
