"""在线学习 - 路由（批次3）。

接口清单：
- POST   /course/videos/upload        视频上传（multipart → MinIO + 建记录）
- GET    /course/videos               视频列表（含是否已生成课程）
- GET    /course/videos/{vid}/stream  视频流（支持 HTTP Range，供 <video> 拖动进度）
- POST   /course/videos/{vid}/course  由视频生成课程 → 返回课程 id（前端跳课程列表）
- GET    /course/courses              课程列表（附带我的学习进度）
- POST   /course/progress             上报学习进度 {course_id, position, duration}
- GET    /course/progress             我的学习进度页（每门课进度 + 最近学习排序）

鉴权：视频流接口用 query token（video 标签 src 无法带 Header），
其余走标准 Bearer。
"""
# hq新增内容 - 在线学习批次3
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Request
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_any_perm, require_permission
from app.core.security import decode_token
from app.dao.course import CourseDAO
from app.dao.course_progress import CourseProgressDAO
from app.dao.course_video import CourseVideoDAO
from app.db.session import get_db
from app.models.user import User
from app.services.course_service import CourseService
from app.utils.object_storage import get_object_storage
from app.utils.response import ok

logger = logging.getLogger(__name__)
router = APIRouter()

# ============ 工具：视频流 Range 支持 ============
def _build_range_response(client, bucket: str, obj_key: str, total: int,
                          mime: str, range_header: str | None) -> Response:
    """按 Range 头构造 206 响应。range_header 形如 bytes=0-1023"""
    start, end = 0, total - 1
    if range_header and range_header.startswith("bytes="):
        try:
            spec = range_header[6:].split("-")
            if spec[0]:
                start = int(spec[0])
            if len(spec) > 1 and spec[1]:
                end = min(int(spec[1]), total - 1)
            if start > end or start < 0:
                start, end = 0, total - 1
        except ValueError:
            start, end = 0, total - 1

    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{total}",
        "Content-Length": str(length),
        "Content-Type": mime,
        "Cache-Control": "no-store",
    }
    try:
        resp = client.get_object(bucket, obj_key, offset=start, length=length)
    except Exception as e:
        logger.warning("[hq] 视频分片读取失败 %s: %s", obj_key, e)
        raise HTTPException(500, f"视频读取失败：{e}")

    def iter_bytes():
        try:
            chunk = resp.read(1024 * 256)
            while chunk:
                yield chunk
                chunk = resp.read(1024 * 256)
        finally:
            resp.close()
            resp.release_conn()

    return StreamingResponse(iter_bytes(), status_code=206, headers=headers)


def _video_stream_response(obj_key: str, content_type: str | None,
                           range_header: str | None) -> Response:
    """从 MinIO 拉视频字节，按 Range 头返回 206 分片。

    使用 minio 的 get_object(offset=..., length=...) 只读需要的分片，避免整段下载。
    """
    storage = get_object_storage()
    try:
        stat = storage._client.stat_object(storage.bucket, obj_key)
        total = stat.size
    except Exception as e:
        logger.warning("[hq] 视频 stat 失败 %s: %s", obj_key, e)
        raise HTTPException(404, "视频文件不存在")
    return _build_range_response(storage._client, storage.bucket, obj_key, total,
                                 content_type or "video/mp4", range_header)


# ============ 上传 ============
@router.post("/videos/upload", summary="上传视频（Multipart → MinIO）")
async def upload_video(
    file: UploadFile = File(...),
    title: str | None = Form(None, description="视频标题，缺省用文件名"),
    description: str | None = Form(None, description="视频简介"),
    user: User = Depends(require_permission("course:video")),
    db: Session = Depends(get_db),
):
    content = await file.read()
    obj = CourseService.upload_video(
        db, content, file.filename or "video.mp4",
        file.content_type or "video/mp4", title, description,
    )
    db.commit()
    return ok({
        "id": obj.id,
        "title": obj.title,
        "object_key": obj.object_key,
        "size": obj.size,
        "has_course": obj.has_course,
        "message": "视频上传成功",
    })


# ============ 视频列表 ============
@router.get("/videos", summary="视频列表（含是否已生成课程）")
def list_videos(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_any_perm("course:video", "training:course")),
):
    """视频素材列表：视频管理(course:video)与培训课程管理(training:course)均可读（挂课节用）。"""
    rows = CourseVideoDAO.list_enabled(db, keyword)
    items = []
    for v in rows:
        course = CourseDAO.get_by_video(db, v.id)
        items.append({
            "id": v.id,
            "title": v.title,
            "description": v.description,
            "content_type": v.content_type,
            "size": v.size,
            "duration": v.duration,
            "has_course": v.has_course,
            "course_id": course.id if course else None,
            "created_at": v.created_at.strftime("%Y-%m-%d %H:%M:%S") if v.created_at else None,
        })
    return ok({"items": items, "total": len(items)})


# ============ 视频流（Range）============
@router.get("/videos/{vid}/stream", summary="视频流（Range 206，供 <video> 播放）")
def stream_video(
    vid: int,
    request: Request,
    token: str | None = Query(None, description="JWT（video 标签无法带 Header，用 query 传）"),
    db: Session = Depends(get_db),
):
    # 鉴权：优先 Header Bearer，其次 query token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        payload = decode_token(auth[7:])
    elif token:
        payload = decode_token(token)
    else:
        raise HTTPException(401, "未登录或登录已过期")
    if not payload or payload.get("type") != "access" or not payload.get("sub"):
        raise HTTPException(401, "未登录或登录已过期")

    video = CourseVideoDAO.get(db, vid)
    if not video or video.status != 1:
        raise HTTPException(404, "视频不存在或已失效")
    return _video_stream_response(video.object_key, video.content_type,
                                  request.headers.get("range"))


# ============ 生成课程 ============
@router.post("/videos/{vid}/course", summary="由视频生成课程（点击「生成课程」）")
def generate_course(
    vid: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("course:course")),
):
    course = CourseService.generate_course(db, vid)
    db.commit()
    return ok({"course_id": course.id, "title": course.title,
               "message": "课程已生成，进入课程列表开始学习"})


# ============ 课程列表 ============
@router.get("/courses", summary="课程列表（附带我的学习进度）")
def list_courses(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("course:course")),
):
    rows = CourseDAO.list_enabled(db, keyword)
    items = []
    for c in rows:
        video = CourseVideoDAO.get(db, c.video_id)
        prog = CourseProgressDAO.get_for_user_course(db, user.id, c.id)
        items.append({
            "id": c.id,
            "video_id": c.video_id,
            "title": c.title,
            "description": c.description,
            "duration": c.duration,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else None,
            "video_ready": bool(video and video.status == 1),
            "progress": {
                "position": prog.position if prog else 0,
                "duration": prog.duration if prog else 0,
                "percent": prog.percent if prog else 0,
                "completed": prog.completed if prog else 0,
                "last_watch_at": (prog.last_watch_at.strftime("%Y-%m-%d %H:%M:%S")
                                  if prog and prog.last_watch_at else None),
            },
        })
    return ok({"items": items, "total": len(items)})


# ============ 上报进度 ============
@router.post("/progress", summary="上报学习进度（播放器定时调用）")
def report_progress(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("course:course")),
):
    course_id = body.get("course_id")
    position = int(body.get("position") or 0)
    duration = int(body.get("duration") or 0)
    if not course_id or not CourseDAO.get(db, course_id):
        raise HTTPException(404, "课程不存在")
    if position < 0:
        raise HTTPException(400, "position 不能为负")
    prog = CourseProgressDAO.upsert(db, user.id, course_id, position=position, duration=duration)
    db.commit()
    return ok({"percent": prog.percent, "completed": prog.completed,
               "message": "进度已更新"})


# ============ 学习进度页 ============
@router.get("/progress", summary="我的学习进度（进度页数据源，含未学习课程）")
def my_progress(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("course:course")),
):
    # hq+  以全部已生成课程为基准：未学习的课程也返回（percent=0），
    #     保证「课程总数 = 未学习 + 学习中 + 已完成」
    courses = CourseDAO.list_enabled(db)
    prog_map = {p.course_id: p for p in CourseProgressDAO.list_for_user(db, user.id)}
    items = []
    for c in courses:
        p = prog_map.get(c.id)
        video = CourseVideoDAO.get(db, c.video_id)
        items.append({
            "course_id": c.id,
            "course_title": c.title,
            "video_id": c.video_id,
            "video_ready": bool(video and video.status == 1),
            "position": p.position if p else 0,
            "duration": p.duration if p else 0,
            "percent": p.percent if p else 0,
            "completed": p.completed if p else 0,
            "last_watch_at": (p.last_watch_at.strftime("%Y-%m-%d %H:%M:%S")
                              if p and p.last_watch_at else None),
        })
    return ok({"items": items, "total": len(items)})
