from datetime import date
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class ApiResp(BaseModel, Generic[T]):
    """统一响应包装：{code, message, data}。

    为什么需要它（踩坑记录）：
      项目后端统一用 ok() 返回 {"code", "message", "data"}，字段都在 data 里。
      若路由直接写 response_model=XxxOut，FastAPI 会拿 XxxOut 去校验「最外层」，
      而字段实际在 data 里 → 报 ResponseValidationError → 接口 500。
      所以用 ApiResp[XxxOut] 标注：既匹配真实响应结构，又能在 /docs 展示 data 内的出参契约。

    与 app/utils/response.py 的 ok() 返回结构一致，
    用于给路由标注 response_model，让 /docs 展示真实出参。
    """
    code: int = Field(0, description="0=成功")
    message: str = Field("ok", description="提示信息")
    data: T | None = Field(None, description="业务数据")


class OverviewOut(BaseModel):
    """GET /analytics/overview 看板概览。"""
    talent_total: int = Field(0, description="人才总量")
    talent_by_degree: dict[str, int] = Field(default_factory=dict, description="学历结构")
    talent_by_level: dict[str, int] = Field(default_factory=dict, description="等级结构 S/A/B/C")
    recruiting_positions: int = Field(0, description="空缺岗位数（启用且 filled < headcount）")
    assess_pass_rate: float = Field(0.0, description="测评合格率(0-1)")
    training_completion_rate: float = Field(0.0, description="培训计划完成率(0-1)")
    match_avg_score: float = Field(0.0, description="平均匹配度(0-100)")


class TrendPoint(BaseModel):
    """GET /analytics/trend 趋势序列单点。"""
    date: str = Field(..., description="统计日期 YYYY-MM-DD")
    count: int = Field(0, description="当日新增/完成数")


class DistributionOut(BaseModel):
    """GET /analytics/distribution 技能/部门分布（饼图数据源）。"""
    items: list[dict] = Field(default_factory=list, description="[{name,value}]")


class NL2SQLRequest(BaseModel):
    """POST /analytics/nl2sql 问数请求（Agent入口）。"""
    question: str = Field(..., min_length=1, description="自然语言问题")
    chart_type: str | None = Field("bar", description="期望图表类型 bar/line/pie")

class DimFilterQuery(BaseModel):
    """GET /analytics/dim-filter 多维筛选入参。
    FastAPI 里 GET 接口用 Depends(DimFilterQuery) 接收，字段自动变成 query 参数，
    /docs 里会渲染成可填的表单项，前端调试不用手写 URL。
    """
    dept_id: int | None = Field(None, description="部门ID，None=全部部门")
    position_id: int | None = Field(None, description="岗位ID，None=全部岗位（精确匹配，与 dept_id 对称）")
    position: str | None = Field(None, description="岗位名称（模糊匹配，会 JOIN pos_position 按名称筛选；与 position_id 二选一或并用）")
    level: str | None = Field(None, description="人才等级 S/A/B/C，None=全部等级")
    start_date: date | None = Field(None, description="统计起始日 YYYY-MM-DD")
    end_date: date | None = Field(None, description="统计截止日 YYYY-MM-DD（含当日）")
    # ③ 时间口径双锚点：result=子域自身记录时间(近30天测评记录)；talent_entry=人才入职时间(近30天入职人才测评)
    time_anchor: Literal["result", "talent_entry"] = Field(
        "result", description="时间口径：result=用子域自身 created_at(记录产生时间)；talent_entry=用 tal_talent.created_at(人才入职时间)")
    # 同比/环比开关：none=只算本期；yoy=同比（比去年同期）；mom=环比（比上一个等长周期）
    compare: Literal["none", "yoy", "mom"] = Field("none", description="对比方式")
    metric: str = Field("talent_total", description="统计指标 talent_total/assess_done/...")

    @model_validator(mode="after")
    def _check_date_range(self):
        """校验时间范围：只传一半无意义，且起止不能颠倒。"""
        if bool(self.start_date) ^ bool(self.end_date):
            raise ValueError("start_date 与 end_date 必须同时传或同时不传")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        return self


class DimFilterOut(BaseModel):
    """出参：本期值 + 对比期值 + 变化率（前端直接渲染卡片）。"""
    metric: str = Field(..., description="指标名")
    # int|float：talent_total 为 int（人才计数）；assess_pass_rate/training_completion_rate
    # 为 float(0-1 比率)、match_avg_score 为 float(0-100)——方案② 2026-09-02 起 metric 真分发
    current: int | float = Field(0, description="本期值（计数 int；比率/匹配度 float）")
    previous: int | float | None = Field(None, description="对比期值，compare=none/全局指标时为 None")
    change_rate: float | None = Field(None, description="变化率(小数)，如 0.15 表示 +15%")

class ExportRequest(BaseModel):
    """POST /analytics/export 报表导出入参。"""
    report_type: str = Field("talent", description="报表类型 talent/assess/match/training")
    filters: dict | None = Field(None, description="筛选条件，字段同 DimFilterQuery")


class ExportOut(BaseModel):
    """导出结果：文件名 + 可供前端直接下载的 URL。"""
    file_name: str = Field(..., description="导出文件名")
    file_url: str = Field(..., description="下载地址（走后端代理，不暴露 MinIO 地址）")

class NL2SQLOut(BaseModel):
    """POST /analytics/nl2sql 出参（D1 骨架字段即最终字段，后续只填值不改结构）。"""
    question: str = Field(..., description="原始问题")
    sql: str | None = Field(None, description="生成的 SQL，拒答或骨架阶段为 None；默认折叠隐藏")
    columns: list[str] = Field(default_factory=list, description="结果列名")
    rows: list[list] = Field(default_factory=list, description="结果数据行")
    chart_json: dict | None = Field(None, description="ECharts option，可直接渲染")
    answer: str | None = Field(None, description="LLM 自然语言解读，HR 友好；默认展示，SQL 折叠")
    status: str = Field("skeleton", description="skeleton/ok/rejected")


