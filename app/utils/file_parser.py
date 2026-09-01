"""文件解析工具（批次 2.3a）。

支持从简历文件抽取纯文本，供 Agent① 调用：
- PDF (.pdf)        pdfminer.six（纯 Python，无需外部进程）
- Word (.docx)      python-docx
- 图片 (.jpg/.jpeg/.png/.bmp/.webp)  pytesseract + Pillow（调用本机 tesseract）
- 文本 (.txt/.md)   直接读

依赖惰性导入：未安装某库时不影响其它模块加载。
- 真依赖：
    pip install pdfminer.six python-docx pillow pytesseract
- 同时本机需装 tesseract（pytesseract 是包装）：
    Windows:  https://github.com/UB-Mannheim/tesseract/wiki 安装并加 PATH
    Mac:      brew install tesseract tesseract-lang
    Linux:    apt-get install tesseract-ocr tesseract-ocr-chi-sim

仅本模块新增。
"""
# hq新增内容 - 人才档案批次 2.3a
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


PDF_SUFFIX = {".pdf"}
DOCX_SUFFIX = {".docx"}
IMG_SUFFIX = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
TEXT_SUFFIX = {".txt", ".md"}

SUPPORTED = PDF_SUFFIX | DOCX_SUFFIX | IMG_SUFFIX | TEXT_SUFFIX

# 简单限流（防止误传超大文件或 OCR 时间过长）
MAX_BYTES = 20 * 1024 * 1024          # 20MB
MAX_CHARS = 200_000                   # 抽出来的文本上限（再长就截断，留给 LLM 自己看）

# OCR 默认中英文混合（覆盖绝大多数简历场景）
DEFAULT_OCR_LANG = "chi_sim+eng"


def is_supported(suffix: str) -> bool:
    """是否支持的文件类型。"""
    return suffix.lower() in SUPPORTED


def detect_kind(suffix: str) -> str:
    s = suffix.lower()
    if s in PDF_SUFFIX:  return "pdf"
    if s in DOCX_SUFFIX: return "docx"
    if s in IMG_SUFFIX:  return "image"
    if s in TEXT_SUFFIX: return "text"
    raise ValueError(f"暂不支持的文件类型：{suffix}")


def parse_file(path: str | Path, *, ocr_lang: str = DEFAULT_OCR_LANG) -> str:
    """从本地路径抽文本。统一异常向上抛，由 service 层 BusinessError 化。"""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{p}")
    size = p.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"文件过大（{size} bytes），上限 {MAX_BYTES} bytes")

    kind = detect_kind(p.suffix)
    text: str

    if kind == "pdf":
        # hq+ 惰性 import：未装 pdfminer 时模块照样能 import
        try:
            from pdfminer.high_level import extract_text
        except ImportError as e:
            raise RuntimeError("PDF 解析依赖缺失：pip install pdfminer.six") from e
        text = extract_text(str(p))

    elif kind == "docx":
        try:
            from docx import Document  # python-docx
        except ImportError as e:
            raise RuntimeError("DOCX 解析依赖缺失：pip install python-docx") from e
        doc = Document(str(p))
        text = "\n".join(par.text for par in doc.paragraphs)

    elif kind == "image":
        # hq+  OCR：pytesseract + Pillow
        try:
            from PIL import Image
            import pytesseract
        except ImportError as e:
            raise RuntimeError(
                "图片 OCR 依赖缺失：pip install pillow pytesseract（并安装本机 tesseract）"
            ) from e
        img = Image.open(str(p))
        text = pytesseract.image_to_string(img, lang=ocr_lang)

    elif kind == "text":
        # hq+  直接读，宽容编码
        text = p.read_text(encoding="utf-8", errors="ignore")

    else:  # pragma: no cover
        raise ValueError(f"暂不支持的文件类型：{p.suffix}")

    text = (text or "").strip()
    if len(text) > MAX_CHARS:
        logger.warning("[hq] 抽出的文本 %d 字符超过上限 %d，已截断", len(text), MAX_CHARS)
        text = text[:MAX_CHARS]
    return text


def parse_bytes(content: bytes, suffix: str, *, ocr_lang: str = DEFAULT_OCR_LANG) -> str:
    """从字节内容抽文本（不落盘）。PDF/DOCX 库一般需要路径，所以走临时文件。"""
    import tempfile
    suffix = suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
    if not is_supported(suffix):
        raise ValueError(f"暂不支持的文件类型：{suffix}")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        return parse_file(tmp_path, ocr_lang=ocr_lang)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:  # pragma: no cover
            pass
