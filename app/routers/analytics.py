"""F 数据决策域路由。
统一走 require_permission 权限码 + ok() 统一响应；接口提交 /docs 供前端并行。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import require_permission
from app.db.session import get_db
from app.services import analytics_service
from fastapi import Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from app.utils.response import ok
from app.core.config import get_settings
from app.core.redis_client import enforce_rate_limit
import io
from app.schemas.analytics import (ApiResp, DimFilterQuery, DimFilterOut,
                                   ExportRequest, ExportOut,
                                   NL2SQLRequest, NL2SQLOut)



router = APIRouter()


@router.get("/overview")
def overview(db: Session = Depends(get_db),
             _=Depends(require_permission("analytics:list"))):
    """看板概览。"""
    return ok(analytics_service.overview(db))


@router.get("/trend")
def trend(metric: str = "talent_new", days: int = 30,
          db: Session = Depends(get_db),
          _=Depends(require_permission("analytics:list"))):
    """趋势（折线图）。"""
    return ok(analytics_service.trend(db, metric, days))


@router.get("/distribution")
def distribution(dimension: str = "degree",
                 db: Session = Depends(get_db),
                 _=Depends(require_permission("analytics:list"))):
    """分布（饼图）。"""
    return ok(analytics_service.distribution(db, dimension))

# ===== D-4 报表导出（F04）=====
# 关键：response_model 必须用 ApiResp[ExportOut]（统一响应包装），不能直接写 ExportOut。
# 因为 ok() 已经返回 {code, message, data}，业务字段在 data 里；
# 若写 response_model=ExportOut，FastAPI 会拿 ExportOut 去校验最外层（实际是 ApiResp 结构）→ 500。
@router.post("/export", response_model=ApiResp[ExportOut])
def export(req: ExportRequest, request: Request,
           db: Session = Depends(get_db),
           _=Depends(require_permission("analytics:export"))):
    """报表导出（F04）：生成 xlsx 上传对象存储，返回下载 URL。

    入参 ExportRequest：{report_type: talent/assess/match/training, filters?, date_range?}
    出参 ExportOut：{file_name, file_url, object_name}
    """
    # 1. 交给 service 层处理：按 report_type 分发取数 → 生成 xlsx → 上传 MinIO 对象存储。
    #    req.model_dump() 把 Pydantic 请求模型转成 dict（service 层统一按 dict 处理，便于复制/改时间范围）。
    result = analytics_service.export_report(db, req.model_dump())

    # 2. 拼出"可下载的 file_url"：
    #    request.url_for("download_report") 反查下载端点的完整路径（自动带 API_PREFIX /api/v1），
    #    再 include_query_params 把 object_name 拼成 query string；
    #    好处：不硬编码 "/api/v1/analytics/export/download"，前缀改了这里也不用改。
    result["file_url"] = str(
        request.url_for("download_report").include_query_params(
            object_name=result["object_name"])
    )

    # 3. 统一响应包装返回：{code:0, message:"ok", data:{file_name, file_url, object_name}}
    return ok(result)


@router.get("/export/download", name="download_report")
def download_report(object_name: str,
                    _=Depends(require_permission("analytics:export"))):
    """下载导出文件：走后端代理读取 MinIO，桶地址不暴露给前端。"""
    from app.utils.object_storage import get_object_storage
    from app.utils.response import BusinessError

    try:
        data = get_object_storage().get_bytes(
            object_name, bucket=analytics_service.REPORT_BUCKET)
    except Exception as exc:
        raise BusinessError(404, f"文件不存在或已过期: {exc}")

    return StreamingResponse(
        io.BytesIO(data),
        media_type=analytics_service._XLSX_CONTENT_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{object_name.split("/")[-1]}"'},
    )

# 同样用 ApiResp 包装，避免 response_model 与 ok() 包装冲突导致的 500
@router.post("/nl2sql", response_model=ApiResp[NL2SQLOut])
async def nl2sql(req: NL2SQLRequest,
                 user=Depends(require_permission("analytics:nl2sql"))):
    """Agent⑤ 问数入口（D2：真实调用引擎，返回 SQL+数据+图表）。"""
    settings = get_settings()
    await run_in_threadpool(
        enforce_rate_limit,
        "analytics-nl2sql",
        str(user.id),
        limit=settings.REDIS_AI_RATE_LIMIT,
        window=settings.REDIS_AI_RATE_WINDOW,
    )
    from app.ai.agents.query_agent import get_query_agent
    from app.services.agent_log_service import log_agent_task, log_conversation
    result = await get_query_agent().run({
        "question": req.question,
        "chart_type": req.chart_type or "bar",
    })
    # 契约出参：sql/columns/rows/chart_json/status
    out = {
        "question": req.question,
        "sql": result.get("sql"),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "chart_json": result.get("chart_json"),
        "status": result.get("status", "failed"),
    }
    # Agent⑤ 落库：ai_agent_task + ai_conversation（失败不阻塞回复）
    try:
        log_agent_task("nl2sql", req.question, result, req.chart_type or "bar")
        answer = "查询结果" if result.get("status") == "done" else f"问数未完成：{result.get('error_msg') or '未知错误'}"
        log_conversation(user.id, "nl2sql", req.question, answer, result.get("chart_json"))
    except Exception as exc:  # noqa: BLE001  落库失败不影响主链路
        import logging
        logging.getLogger("agent_log").warning("nl2sql 落库失败: %s", exc)
    return ok(out)

# 同样用 ApiResp 包装，避免 response_model 与 ok() 包装冲突导致的 500
@router.get("/dim-filter", response_model=ApiResp[DimFilterOut])
def dim_filter(q: DimFilterQuery = Depends(),
               db: Session = Depends(get_db),
               _=Depends(require_permission("analytics:list"))):
    """多维筛选（F02），支持同比/环比。"""
    return ok(analytics_service.dim_filter(db, q))
