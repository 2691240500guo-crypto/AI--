"""F 域聚合 DAO。
规约：F 域不建存量表，只读聚合 T/A/M/TR 各域表；
     严格 router→service→dao 单向依赖，本层只做查询不做业务判断。
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.utils.logger import logger  # 按基座实际logger名微调
from datetime import date, datetime, time


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


def assess_pass_rate(db: Session) -> float:
    """测评合格率（A 域 asm_result，负责人 P4）：status=2/3 视为已交卷，按约定口径调整。"""
    # TODO(P10): 与 P4 确认"合格"口径（score 阈值 or 状态位）后填实现
    return 0.0


def training_completion_rate(db: Session) -> float:
    """培训完成率（TR 域 trn_training_plan，负责人 P8）。"""
    # TODO(P10): 与 P8 确认 plan.status 完成态取值后填实现
    return 0.0


def match_avg_score(db: Session) -> float:
    """平均匹配度（M 域 match_result，负责人 P6）。"""
    # TODO(P10): 与 P6 确认 score 满分制(0-100)后填实现
    return 0.0


# ===== 多维筛选：列白名单 =====
# 只允许通过这份字典取出模型列对象；用户输入永远只当「值」用，绝不当「列名/SQL片段」用。
# key = 请求参数名（对前端暴露），value = (模型字段名, 匹配方式)
_TALENT_COLUMNS: dict[str, tuple[str, str]] = {
    "dept_id": ("dept_id", "eq"),      # 精确匹配
    "level": ("level", "eq"),          # 精确匹配，如 S/A/B/C
    "position": ("position", "like"),  # 模糊匹配，如 "算法"
}
_TIME_COLUMN = "created_at"            # 时间范围统一走该列（与 P2 确认列名后一致即可）


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
        return db.scalar(select(func.count(Talent.id)).where(*conds)) or 0
    except Exception as exc:                      # 表未建 / 字段不符等一律降级
        logger.warning("talent_filter 降级: %s", exc)
        return 0
