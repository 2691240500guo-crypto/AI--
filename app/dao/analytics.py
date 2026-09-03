"""F 域聚合 DAO。
规约：F 域不建存量表，只读聚合 T/A/M/TR 各域表；
     严格 router→service→dao 单向依赖，本层只做查询不做业务判断。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.utils.logger import logger  # 按基座实际logger名微调
from datetime import date, datetime, time, timedelta


def talent_total(db: Session) -> int:
    """人才总量（T 域 tal_talent，负责人 P2）。"""
    try:
        from app.models.talent import Talent          # 惰性导入：模型未合入时走降级
        return db.scalar(select(func.count(Talent.id))) or 0
    except Exception as exc:                          # ImportError 或表未建
        logger.warning("tal_talent 未就绪，talent_total 返回 0: %s", exc)
        return 0


def talent_by_degree(db: Session) -> dict[str, int]:
    """学历结构分布：group by degree（饼图数据源）。"""
    try:
        from app.models.talent import Talent
        rows = db.execute(
            select(Talent.degree, func.count(Talent.id)).group_by(Talent.degree)
        ).all()
        return {degree or "未知": cnt for degree, cnt in rows}
    except Exception as exc:
        logger.warning("talent_by_degree 降级: %s", exc)
        return {}


def _time_cond(model, start_date, end_date):
    """构造时间窗口条件：model.created_at BETWEEN [start_date 00:00:00] AND [end_date 23:59:59.999999]。

    仅当 start_date 与 end_date 均非空、且模型确有 created_at 列时返回条件；
    否则返回 None（不过滤）。用于全局指标在指定周期内重算对比期值。
    注意：start/end 入参是 date，而 created_at 多为 DATETIME，故结束日用 time.max
    推到当天末、起始日用 time.min，保证「含当日」（与 daily_new_counts 既有写法一致）。
    """
    if start_date is None or end_date is None:
        return None
    col = getattr(model, "created_at", None)
    if col is None:
        logger.warning("%s 缺少 created_at 列，时间窗口被忽略", getattr(model, "__name__", model))
        return None
    return col.between(datetime.combine(start_date, time.min),
                      datetime.combine(end_date, time.max))


def assess_pass_rate(db: Session, start_date=None, end_date=None) -> float:
    """测评合格率（A 域 asm_result，负责人 P4）。

    口径暂定：status in (2,3)（交卷/出报告）且 score >= 60 视为合格。
    start_date/end_date：可选时间窗口（按 AssessmentResult.created_at 过滤），
        不传 = 全量（兼容 overview 看板全局口径调用）。
    TODO(P10): P4 确认后可能改为只看状态位、或不同阈值——确认后只改这一处。
    """
    try:
        from app.models.assessment import AssessmentResult  # P4 的类名是 AssessmentResult
        time_cond = _time_cond(AssessmentResult, start_date, end_date)
        base_total = select(func.count(AssessmentResult.id))
        base_passed = select(func.count(AssessmentResult.id)).where(
            AssessmentResult.status.in_([2, 3]), AssessmentResult.score >= 60
        )
        if time_cond is not None:
            base_total = base_total.where(time_cond)
            base_passed = base_passed.where(time_cond)
        total = db.scalar(base_total) or 0
        if total == 0:
            return 0.0
        passed = db.scalar(base_passed) or 0
        return round(passed / total, 4)
    except Exception as exc:
        logger.warning("assess_pass_rate 降级: %s", exc)
        return 0.0


def training_completion_rate(db: Session, start_date=None, end_date=None) -> float:
    """培训计划完成率（TR 域 trn_training_plan，负责人 P8）：status=2 表示已完成。
    start_date/end_date：可选时间窗口（按 TrainingPlan.created_at 过滤），不传 = 全量。
    """
    try:
        from app.models.training import TrainingPlan   # 惰性导入，沿用文件风格
        time_cond = _time_cond(TrainingPlan, start_date, end_date)
        base_total = select(func.count(TrainingPlan.id))
        base_done = select(func.count(TrainingPlan.id)).where(TrainingPlan.status == 2)
        if time_cond is not None:
            base_total = base_total.where(time_cond)
            base_done = base_done.where(time_cond)
        total = db.scalar(base_total) or 0
        if total == 0:
            return 0.0
        done = db.scalar(base_done) or 0
        return round(done / total, 4)
    except Exception as exc:                            # 表未建/字段不符时降级，不拖垮看板
        logger.warning("training_completion_rate 降级: %s", exc)
        return 0.0


def match_avg_score(db: Session, start_date=None, end_date=None) -> float:
    """平均匹配度（M 域 match_result，负责人 P6）：score 满分 0-100。
    start_date/end_date：可选时间窗口（按 MatchResult.created_at 过滤），不传 = 全量。
    """
    try:
        from app.models.matching import MatchResult
        time_cond = _time_cond(MatchResult, start_date, end_date)
        q = select(func.avg(MatchResult.score))
        if time_cond is not None:
            q = q.where(time_cond)
        avg = db.scalar(q)
        return float(avg) if avg is not None else 0.0
    except Exception as exc:
        logger.warning("match_avg_score 降级: %s", exc)
        return 0.0



# ===== 多维筛选：列白名单 =====
# 只允许通过这份字典取出模型列对象；用户输入永远只当「值」用，绝不当「列名/SQL片段」用。
# key = 请求参数名（对前端暴露），value = (模型字段名, 匹配方式)
_TALENT_COLUMNS: dict[str, tuple[str, str]] = {
    "dept_id": ("dept_id", "eq"),        # 精确匹配
    "level": ("level", "eq"),            # 精确匹配，如 S/A/B/C
    "position_id": ("position_id", "eq"),# 精确匹配岗位ID（tal_talent.position_id 是真实外键列，不再误用不存在的 position 文本列）
    # 注：岗位名称模糊（position 参数）不走白名单，由 _apply_position_name_filter 单独 JOIN pos_position 处理
}
_TIME_COLUMN = "created_at"            # 时间范围统一走该列（与 P2 确认列名后一致即可）


def _apply_position_name_filter(query, filters):
    """岗位名称模糊匹配：需 JOIN pos_position（tal_talent 只存 position_id，不存名称文本）。

    - filters 里 "position" 参数（岗位名）非空 → JOIN pos_position 并按名称模糊过滤；
    - "position_id" 由白名单精确处理，不走这里（无需额外 JOIN）。
    模型未合入/字段缺失时降级跳过，不硬崩、不拖垮其他筛选条件。
    """
    name = (filters or {}).get("position")
    if name in (None, ""):
        return query
    try:
        from app.models.talent import Talent
        from app.models.matching import PosPosition
    except Exception as exc:
        logger.warning("岗位名称筛选依赖模型未就绪，忽略: %s", exc)
        return query
    query = query.join(PosPosition, Talent.position_id == PosPosition.id)
    query = query.where(PosPosition.name.like(f"%{name}%"))
    return query


def talent_filter(db: Session, filters) -> int:
    """多维筛选计数（F02）：按 dept_id / level / position / 时间范围 过滤统计人才数。

    防注入三原则（本函数严格遵循）：
      ① 列名只能从 _TALENT_COLUMNS / _TIME_COLUMN 白名单取，用户传什么都不改列名
      ② 用户值一律交给 SQLAlchemy 做绑定参数（col == val），即使传 "1 OR 1=1"
         也只会被当成普通字符串去比对，不会拼进 SQL 文本
      ③ 模型字段缺失（P2 还没加该字段）时跳过条件并打日志，不硬崩、不改别人的代码

    入参 filters：DimFilterQuery 实例或 dict，字段缺失即视为不限制该维度。
    """
    try:
        from app.models.talent import Talent      # 惰性导入：模型未合入时走降级
    except Exception as exc:
        logger.warning("tal_talent 未就绪，talent_filter 返回 0: %s", exc)
        return 0

    try:
        # 兼容 Pydantic 模型与 dict 两种入参（service 层怎么传都能跑）
        f = filters if isinstance(filters, dict) else filters.model_dump()

        conds = []
        # ---- 1. 等值 / 模糊条件：只从白名单取列 ----
        for param, (col_name, op) in _TALENT_COLUMNS.items():
            val = f.get(param)
            if val in (None, ""):                 # 没传该维度 = 不限制
                continue
            col = getattr(Talent, col_name, None) # 模型没有该字段则跳过（不阻塞其他条件）
            if col is None:
                logger.warning("tal_talent 缺少字段 %s，跳过筛选条件 %s", col_name, param)
                continue
            conds.append(col.like(f"%{val}%") if op == "like" else col == val)

        # ---- 2. 时间范围：起止都传才生效，截止日补到 23:59:59 避免漏掉当天 ----
        start: date | None = f.get("start_date")
        end: date | None = f.get("end_date")
        time_col = getattr(Talent, _TIME_COLUMN, None)
        if start is not None and end is not None and time_col is not None:
            conds.append(time_col.between(
                datetime.combine(start, time.min),  # 00:00:00
                datetime.combine(end, time.max),  # 23:59:59.999999
            ))

        # ---- 3. 执行：无条件时也返回全量计数（conds 为空 => 只 count）----
        # 岗位名称模糊需 JOIN pos_position
        query = select(func.count(Talent.id))
        query = _apply_position_name_filter(query, f)
        return db.scalar(query.where(*conds)) or 0
    except Exception as exc:                      # 表未建 / 字段不符等一律降级
        logger.warning("talent_filter 降级: %s", exc)
        return 0

def daily_new_counts(db: Session, model_key: str, days: int = 30,
                     start: date | None = None, end: date | None = None) -> list[dict]:
    """近 N 天每日新增计数（按 created_at 分组，无数据的天补 0，保证折线连续）。

    模型白名单：model_key 只取这里定义的键，防止任意传参。
    talent/asm_result 模型未合入时走降级返回空，不阻塞其他指标。
    时间窗口：显式传 start/end 优先；否则按 days 往前推（默认近 N 天）。
    """
    import importlib
    _MODELS = {
        "training_plan": ("app.models.training", "TrainingPlan", "created_at"),
        "match_result": ("app.models.matching", "MatchResult", "created_at"),
        "talent": ("app.models.talent", "Talent", "created_at"),
        "asm_result": ("app.models.assessment", "AssessmentResult", "created_at")  # P4 的类名是 AssessmentResult
    }
    if model_key not in _MODELS:
        logger.warning("trend 未知指标 %s，返回空", model_key)
        return []

    mod_path, cls_name, time_col = _MODELS[model_key]
    try:
        Model = getattr(importlib.import_module(mod_path), cls_name)
    except Exception as exc:                        # 模型未合入 → 降级
        logger.warning("%s 模型未就绪，trend 返回空: %s", model_key, exc)
        return []

    col = getattr(Model, time_col)
    # 时间窗口：显式 start/end 优先，否则按 days 往前推
    if start is not None and end is not None:
        window_start, window_end = start, end
        rows = db.execute(
            select(func.date(col).label("d"), func.count(Model.id))
            .where(col.between(datetime.combine(start, time.min),
                              datetime.combine(end, time.max)))
            .group_by(func.date(col))
        ).all()
    else:
        today = date.today()
        window_start = today - timedelta(days=days - 1)
        window_end = today
        rows = db.execute(
            select(func.date(col).label("d"), func.count(Model.id))
            .where(col >= datetime.combine(window_start, time.min))
            .group_by(func.date(col))
        ).all()
    by_day = {str(d): c for d, c in rows}
    # 补零：缺的天也返回 0，前端折线图才连续
    span = (window_end - window_start).days + 1
    return [{"date": (window_start + timedelta(days=i)).strftime("%Y-%m-%d"),
             "count": by_day.get((window_start + timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
            for i in range(span)]

def distribution_items(db: Session, dimension: str) -> list[dict]:
    """分布数据（饼图数据源）：[{name, value}]。dimension 走白名单分发。
    字段口径：严格按需求文档 §3.2 —— tal_talent 用 degree/level 字段名，
    P2 的表后续对齐到文档后本函数直接生效，无需改动。
    """
    try:
        from app.models.talent import Talent          # 模型未合入时走 except 降级

        # ---- 岗位分布：基于已合入的 match_result + pos_position ----
        if dimension == "position":
            from app.models.matching import MatchResult, PosPosition
            rows = db.execute(
                select(PosPosition.name, func.count(MatchResult.id))
                .join(PosPosition, MatchResult.position_id == PosPosition.id)
                .group_by(PosPosition.id)
                .order_by(func.count(MatchResult.id).desc())
            ).all()
            return [{"name": n or "未知", "value": c} for n, c in rows]

        # ---- 部门分布：直接基于 tal_talent.dept_id（与「人才总量」口径一致）----
        if dimension == "dept":
            from app.models.dept import Dept
            rows = db.execute(
                select(func.coalesce(Dept.name, "未分配"), func.count(Talent.id))
                .outerjoin(Dept, Talent.dept_id == Dept.id)
                .group_by(Dept.id)
                .order_by(func.count(Talent.id).desc())
            ).all()
            return [{"name": n, "value": c} for n, c in rows]

        if dimension == "degree":                     # 学历分布（文档字段 degree）
            rows = db.execute(
                select(func.coalesce(Talent.degree, "未知"), func.count(Talent.id))
                .group_by(Talent.degree)
                .order_by(func.count(Talent.id).desc())
            ).all()
            return [{"name": n, "value": c} for n, c in rows]

        if dimension == "level":                      # 等级分布（文档字段 level，S/A/B/C）
            rows = db.execute(
                select(func.coalesce(Talent.level, "未知"), func.count(Talent.id))
                .group_by(Talent.level)
                .order_by(func.count(Talent.id).desc())
            ).all()
            return [{"name": n, "value": c} for n, c in rows]

        if dimension == "skill":                      # 技能分布（分号/逗号分隔文本，只按标点拆）
            import re
            from collections import Counter
            raw = db.execute(select(Talent.skills)).scalars().all()
            cnt: Counter[str] = Counter()
            for s in raw:
                if not s:
                    continue
                for sk in re.split(r"[;,；，]+", str(s)):   # 空格是技能名一部分，不能拆！
                    sk = sk.strip()
                    if sk:
                        cnt[sk] += 1
            return [{"name": k, "value": v} for k, v in cnt.most_common(20)]

        logger.warning("distribution 未知维度 %s，返回空", dimension)
        return []
    except Exception as exc:
        logger.warning("distribution_items(%s) 降级: %s", dimension, exc)
        return []

def talent_rows(db: Session, filters: dict | None = None,
                limit: int = 50_000) -> list[list]:   # 与 service 层 MAX_EXPORT_ROWS 保持一致

    """按白名单筛选取人才行（导出用）：[[id, name, degree, level, dept_id], ...]。

    字段严格按需求文档 §3.2（degree/level/dept_id），P2 表对齐后自动生效；
    复用 _TALENT_COLUMNS 白名单，与 talent_filter 口径一致，防注入。
    """
    try:
        from app.models.talent import Talent          # 模型未合入时走降级
    except Exception as exc:
        logger.warning("tal_talent 未就绪，talent_rows 返回空: %s", exc)
        return []

    try:
        f = filters or {}
        conds = []
        # 1. 白名单条件（和 talent_filter 完全一致）
        for param, (col_name, op) in _TALENT_COLUMNS.items():
            val = f.get(param)
            if val in (None, ""):
                continue
            col = getattr(Talent, col_name, None)
            if col is None:                            # 字段缺失则跳过，不硬崩
                logger.warning("tal_talent 缺少字段 %s，跳过筛选条件 %s", col_name, param)
                continue
            conds.append(col.like(f"%{val}%") if op == "like" else col == val)
        # 2. 时间范围
        start, end = f.get("start_date"), f.get("end_date")
        time_col = getattr(Talent, _TIME_COLUMN, None)
        if start and end and time_col is not None:
            conds.append(time_col.between(
                datetime.combine(start, time.min),
                datetime.combine(end, time.max),
            ))
        # 3. 取行（列与 REPORT_DEFS["talent"] 表头对应：ID/姓名/学历/等级/部门ID）
        # 岗位名称模糊需 JOIN pos_position
        query = select(Talent.id, Talent.name, Talent.degree,
                       Talent.level, Talent.dept_id)
        query = _apply_position_name_filter(query, f)
        rows = db.execute(query.where(*conds).limit(limit)).all()
        return [list(r) for r in rows]
    except Exception as exc:
        logger.warning("talent_rows 降级: %s", exc)
        return []

def _join_talent_if_filtered(query, Model, filters):
    """①②③④ 统一处理人才维度筛选 + 双时间锚。

    ① 部门口径：统一走 tal_talent.dept_id（不再用 match_result 计数）。
    ② 等级口径：统一走 tal_talent.level（S/A/B/C）。
    ③ 时间口径（两个指标都保留、分开命名）：
       - time_anchor="result"（默认）：用子域自身 created_at（记录产生时间）
         → 即「近30天测评记录数/匹配新增/培训新增」，无需 JOIN。
       - time_anchor="talent_entry"：用 tal_talent.created_at（人才入职时间，产品词典约定）
         → 即「近30天入职人才测评/匹配/培训」，需 JOIN tal_talent。
    ④ 悬空关联：仅当存在人才维度条件（dept/level/talent_entry 时间）时才 JOIN，
       无筛选时直接统计/导出子域表全量，保留 talent_id 关联不到 tal_talent 的悬空行。
    """
    from app.models.talent import Talent

    def _as_date(v):
        """兼容 date 对象与 JSON 字符串（导出 filters 是裸 dict，日期为字符串）。"""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        try:
            return date.fromisoformat(str(v)[:10])
        except Exception:
            return None

    f = filters or {}
    talent_conds = []   # 需 JOIN tal_talent 的人才维度条件
    model_conds = []    # 子域自身条件（无需 JOIN）

    # ①② 部门 / 等级 / 岗位：统一走 tal_talent
    if f.get("dept_id") not in (None, ""):
        talent_conds.append(Talent.dept_id == f["dept_id"])
    if f.get("level") not in (None, ""):
        talent_conds.append(Talent.level == f["level"])
    if f.get("position_id") not in (None, ""):
        talent_conds.append(Talent.position_id == f["position_id"])

    # ③ 时间：双锚点
    start, end = _as_date(f.get("start_date")), _as_date(f.get("end_date"))
    if start is not None and end is not None:
        lo, hi = datetime.combine(start, time.min), datetime.combine(end, time.max)
        if f.get("time_anchor") == "talent_entry":
            # 人才入职时间 → 必须 JOIN tal_talent
            talent_conds.append(Talent.created_at.between(lo, hi))
        else:
            # 子域记录产生时间 → 不 JOIN（默认口径）
            model_conds.append(Model.created_at.between(lo, hi))

    if talent_conds:
        query = query.join(Talent, Model.talent_id == Talent.id)
        query = query.where(*talent_conds)
    if model_conds:
        query = query.where(*model_conds)
    return query


def assess_rows(db: Session, filters: dict | None = None, limit: int = 50_000) -> list[list]:
    """测评结果导出取数（A 域 asm_result，负责人 P4）。

    ④ 悬空关联处理：部门/等级等人才维度筛选才 JOIN tal_talent；无筛选则不 JOIN，
    保留 talent_id 关联不到人才的悬空行（全量）。
    """
    try:
        from app.models.assessment import AssessmentResult
    except Exception as exc:
        logger.warning("asm_result 未就绪，assess_rows 返回空: %s", exc)
        return []
    try:
        f = filters or {}
        conds = []
        if f.get("talent_id"):
            conds.append(AssessmentResult.talent_id == f["talent_id"])
        query = select(
            AssessmentResult.id, AssessmentResult.talent_id,
            AssessmentResult.status, AssessmentResult.score,
        )
        if conds:
            query = query.where(*conds)
        query = _join_talent_if_filtered(query, AssessmentResult, f)
        rows = db.execute(query.limit(limit)).all()
        return [[r[0], r[1], r[2], float(r[3]) if r[3] is not None else None] for r in rows]
    except Exception as exc:
        logger.warning("assess_rows 降级: %s", exc)
        return []

def match_rows(db: Session, filters: dict | None = None, limit: int = 50_000) -> list[list]:
    """匹配结果导出取数（M 域 match_result，负责人 P6）。

    ④ 悬空关联处理：人才维度筛选才 JOIN tal_talent；无筛选则不 JOIN 保留全量。
    """
    try:
        from app.models.matching import MatchResult
    except Exception as exc:
        logger.warning("match_result 未就绪，match_rows 返回空: %s", exc)
        return []
    try:
        f = filters or {}
        conds = []
        if f.get("talent_id"):
            conds.append(MatchResult.talent_id == f["talent_id"])
        query = select(
            MatchResult.id, MatchResult.talent_id,
            MatchResult.position_id, MatchResult.score,
        )
        if conds:
            query = query.where(*conds)
        query = _join_talent_if_filtered(query, MatchResult, f)
        rows = db.execute(query.limit(limit)).all()
        return [[r[0], r[1], r[2], float(r[3]) if r[3] is not None else None] for r in rows]
    except Exception as exc:
        logger.warning("match_rows 降级: %s", exc)
        return []

def training_rows(db: Session, filters: dict | None = None, limit: int = 50_000) -> list[list]:
    """培训计划导出取数（TR 域 trn_training_plan，负责人 P8）。

    ④ 悬空关联处理：人才维度筛选才 JOIN tal_talent；无筛选则不 JOIN 保留全量。
    """
    try:
        from app.models.training import TrainingPlan
    except Exception as exc:
        logger.warning("trn_training_plan 未就绪，training_rows 返回空: %s", exc)
        return []
    try:
        f = filters or {}
        conds = []
        if f.get("talent_id"):
            conds.append(TrainingPlan.talent_id == f["talent_id"])
        query = select(
            TrainingPlan.id, TrainingPlan.talent_id,
            TrainingPlan.title, TrainingPlan.status,
        )
        if conds:
            query = query.where(*conds)
        query = _join_talent_if_filtered(query, TrainingPlan, f)
        rows = db.execute(query.limit(limit)).all()
        # status: 0未开始 1进行中 2已完成（替代 REPORT_DEFS 里的"进度"列）
        _ST = {0: "未开始", 1: "进行中", 2: "已完成"}
        return [[r[0], r[1], r[2], _ST.get(r[3], str(r[3]))] for r in rows]
    except Exception as exc:
        logger.warning("training_rows 降级: %s", exc)
        return []

def talent_by_level(db: Session) -> dict[str, int]:
    """等级结构分布（T 域 tal_talent，负责人 P2）：group by level（S/A/B/C，需求文档字段）。

    模型未合入时返回 {}，合入后自动生效；P2 若没建 level 列需找他补。
    """
    try:
        from app.models.talent import Talent          # 惰性导入：模型未合入时走降级
        rows = db.execute(
            select(Talent.level, func.count(Talent.id)).group_by(Talent.level)
        ).all()
        return {level or "未知": cnt for level, cnt in rows}
    except Exception as exc:
        logger.warning("talent_by_level 降级: %s", exc)
        return {}
