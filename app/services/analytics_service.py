"""F 域业务编排。
职责：逐指标聚合、异常降级、必要时加 Redis 缓存（看板 <2s 口径）。
"""
from sqlalchemy.orm import Session
from app.dao import analytics as analytics_dao
from datetime import date, datetime, timedelta
from app.utils.logger import logger
from app.utils.response import BusinessError



def overview(db: Session) -> dict:
    """看板概览：一次返回全部卡片指标（D-1）。"""
    return {
        "talent_total": analytics_dao.talent_total(db),
        "talent_by_degree": analytics_dao.talent_by_degree(db),
        "talent_by_level": analytics_dao.talent_by_level(db),
        "assess_pass_rate": analytics_dao.assess_pass_rate(db),
        "training_completion_rate": analytics_dao.training_completion_rate(db),
        "match_avg_score": analytics_dao.match_avg_score(db),
    }


def trend(db: Session, metric: str, days: int = 30) -> list[dict]:
    """趋势序列（D-1 折线图）。metric: talent_new / training_new / match_new / assess_done。"""
    _METRIC_MAP = {
        "talent_new": "talent",
        "assess_done": "asm_result",
        "training_new": "training_plan",
        "match_new": "match_result",
    }
    key = _METRIC_MAP.get(metric)
    if not key:
        logger.warning("trend 未知 metric=%s，返回空", metric)
        return []
    return analytics_dao.daily_new_counts(db, key, days)


def distribution(db: Session, dimension: str) -> list[dict]:
    """分布数据（D-1 饼图）。dimension: degree / level / skill / position / dept。"""
    _ALLOWED = {"degree", "level", "skill", "position", "dept"}
    if dimension not in _ALLOWED:
        logger.warning("distribution 未知维度 %s，返回空", dimension)
        return []
    return analytics_dao.distribution_items(db, dimension)


def _shift_period(start: date, end: date, compare: str) -> tuple[date, date]:
    """把时间窗口整体前移一个对比周期。

    mom(环比)：前移「本期长度」，本期 8/1~8/31 则上期 7/2~7/31
    yoy(同比)：前移一年，优先用"去年同月同日"，闰年 2/29 兜底为 2/28
    """
    if compare == "mom":
        span = (end - start).days + 1          # 含首含尾，所以 +1
        return start - timedelta(days=span), end - timedelta(days=span)
    try:
        return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
    except ValueError:                          # 2 月 29 日 → 平年不存在
        return start.replace(year=start.year - 1, day=28), end.replace(year=end.year - 1, day=28)


def dim_filter(db: Session, filters) -> dict:
    """多维筛选 + 同比环比（F02）。

    返回：{"metric", "current", "previous", "change_rate"}
      - compare="none" 时 previous / change_rate 均为 None（前端就不渲染对比标签）
      - 未传时间范围时无法定位对比期，previous 为 None 并打日志，不报错
      - previous=0 时 change_rate 为 None，避免除零（前端显示"—"而不是 Infinity）
    """
    # 统一转成 dict：后面要复制一份改时间范围，dict 比模型对象好操作
    params = filters if isinstance(filters, dict) else filters.model_dump()
    metric = params.get("metric") or "talent_total"
    compare = params.get("compare") or "none"
    start, end = params.get("start_date"), params.get("end_date")

    current = analytics_dao.talent_filter(db, params)

    previous: int | None = None
    change_rate: float | None = None
    if compare != "none":
        if not (start and end):
            # 没有时间范围就没有"上期"的概念，降级为只返回本期，不阻塞接口
            logger.warning("compare=%s 但未传时间范围，跳过对比期计算", compare)
        else:
            prev_start, prev_end = _shift_period(start, end, compare)
            prev_params = {**params, "start_date": prev_start, "end_date": prev_end}
            previous = analytics_dao.talent_filter(db, prev_params)
            change_rate = round((current - previous) / previous, 4) if previous else None

    return {
        "metric": metric,
        "current": current,
        "previous": previous,
        "change_rate": change_rate,
    }


REPORT_BUCKET = "report-export"          # 导出产物专用桶
_XLSX_CONTENT_TYPE = ("application/vnd.openxmlformats-officedocument"
                      ".spreadsheetml.sheet")

# 报表字段白名单：外部只能选报表类型，不能指定列——防越权导出敏感字段（如密码哈希）
# 结构：{类型: (表头列表, sheet 名称)}
REPORT_DEFS: dict[str, tuple[list[str], str]] = {
    "talent":   (["ID", "姓名", "学历", "等级", "部门ID"], "人才报表"),
    "assess":   (["ID", "人才ID", "测评状态", "得分"], "测评报表"),
    "match":    (["ID", "人才ID", "岗位ID", "匹配度"], "匹配报表"),
    "training": (["ID", "人才ID", "培训计划", "进度"], "培训报表"),
}
MAX_EXPORT_ROWS = 50_000        # 单次导出行数上限，防一次导出拖垮数据库

def _require_openpyxl():
    """依赖守卫：openpyxl 未安装时给出明确提示，而不是抛裸 ImportError。"""
    try:
        from openpyxl import Workbook  # noqa: F401
    except ImportError as exc:
        raise BusinessError(503, "导出依赖未安装，请联系管理员执行 pip install openpyxl") from exc


def build_excel(headers: list[str], rows: list[list], sheet_title: str = "报表") -> bytes:
    """生成 xlsx 字节流（内存中完成，不落盘，直接上传对象存储）。

    规约：文件里只写数据，不做权限过滤——权限在 router 层用 require_permission 把关，
         数据筛选在 dao 层用白名单过滤，本函数只负责"把二维数据变成文件"。
    """
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    _require_openpyxl()

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]                      # Excel 表名上限 31 字符

    # ---- 1. 表头：加粗 + 底色 + 冻结首行（数据多时表头始终可见）----
    ws.append(headers)
    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="4472C4")
    for cell in ws[1]:
        cell.font = head_font
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"

    # ---- 2. 数据行：None 写空串，避免 Excel 里显示 "None" 字符串 ----
    for row in rows:
        ws.append(["" if v is None else v for v in row])

    # ---- 3. 自动列宽：按最长内容 +2 留白，中文按 2 个字符宽估算 ----
    for idx, header in enumerate(headers, start=1):
        max_len = len(str(header))
        for row in rows:
            val = str(row[idx - 1]) if row[idx - 1] is not None else ""
            # 中日韩字符视觉宽度约为英文 2 倍，按此折算
            width = sum(2 if ord(ch) > 127 else 1 for ch in val)
            max_len = max(max_len, width)
        ws.column_dimensions[get_column_letter(idx)].width = min(max_len + 2, 50)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()

def _fetch_rows(db: Session, report_type: str, filters: dict) -> list[list]:
    """按报表类型取数（导出用）。filters 透传 DAO 白名单，与看板口径一致。"""
    logger.info("导出取数 report_type=%s filters=%s", report_type, filters)
    if report_type == "talent":
        return analytics_dao.talent_rows(db, filters)
    # TODO(P10): assess / match / training 报表取数（等对应模型字段确认后补）
    logger.warning("报表类型 %s 取数未实现，导出空表", report_type)
    return []



def export_report(db: Session, params: dict) -> dict:
    """报表导出主流程（F04）：取数 → 生成 xlsx → 上传 report-export 桶。"""
    _require_openpyxl()                              # ← 新增：依赖守卫，最前面
    report_type = params.get("report_type") or "talent"   # ← 新增：从入参取报表类型
    if report_type not in REPORT_DEFS:
        raise BusinessError(400, f"不支持的报表类型: {report_type}")
    headers, title = REPORT_DEFS[report_type]

    filters = params.get("filters") or {}          # ← 入参 filters 在这里接进来
    rows = _fetch_rows(db, report_type, filters)

    # 数据量兜底：单表导出上限 5 万行，防止一次导出拖垮数据库
    if len(rows) > MAX_EXPORT_ROWS:          #单表导出上限 5 万行,对应dao层def talent_rows(...limit: int = 50_000)
        raise BusinessError(400, f"导出数据量过大（{len(rows)} 行），请缩小筛选范围")

    data = build_excel(headers, rows, title)
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")   # 防同名覆盖上一次导出
    file_name = f"{report_type}_{stamp}.xlsx"
    object_name = f"analytics/{date.today():%Y/%m}/{file_name}"

    try:
        from app.utils.object_storage import get_object_storage
        get_object_storage().put_bytes(
            object_name, data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            bucket=REPORT_BUCKET,
        )
    except ImportError as exc:                       # minio 没装
        raise BusinessError(503, "对象存储依赖未安装，请联系管理员启用 minio") from exc
    except Exception as exc:                         # MinIO 连不上 / 权限不足
        logger.warning("报表上传失败: %s", exc)
        raise BusinessError(500, "报表上传失败，请稍后重试")

    return {"file_name": file_name, "object_name": object_name}
