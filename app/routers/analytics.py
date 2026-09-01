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
from app.utils.response import ok
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

# 用 ApiResp 包装：ok() 返回 {code,message,data}，直接写 ExportOut 会 500（字段在 data 里）
@router.post("/export", response_model=ApiResp[ExportOut])
def export(req: ExportRequest, request: Request,
           db: Session = Depends(get_db),
           _=Depends(require_permission("analytics:export"))):
    """报表导出（F04）：生成 xlsx 上传对象存储，返回下载 URL。"""
    result = analytics_service.export_report(db, req.model_dump())
    # 用 url_for 反查，API_PREFIX 改了也不用改这里（不硬编码 /api）
    result["file_url"] = str(
        request.url_for("download_report").include_query_params(
            object_name=result["object_name"])
    )
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
                 _=Depends(require_permission("analytics:nl2sql"))):
    """Agent⑤ 问数入口（D1 骨架：接收自然语言，返回统一结构的占位响应）。

    D1 不调用 Agent（run() 尚未实现），先固定返回 skeleton 状态，
    保证 P11 前端今天就能对着这套字段结构开始写页面。
    """
    return ok({
        "question": req.question,
        "sql": None,
        "columns": [],
        "rows": [],
        "chart_json": None,
        "status": "skeleton",
    })

# 同样用 ApiResp 包装，避免 response_model 与 ok() 包装冲突导致的 500
@router.get("/dim-filter", response_model=ApiResp[DimFilterOut])
def dim_filter(q: DimFilterQuery = Depends(),
               db: Session = Depends(get_db),
               _=Depends(require_permission("analytics:list"))):
    """多维筛选（F02），支持同比/环比。"""
    return ok(analytics_service.dim_filter(db, q))
