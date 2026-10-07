"""五库连通性自检聚合（M0：/health 扩展面板）。

覆盖：MySQL / Milvus / Redis / Neo4j / PgSQL。
原则：
- 每个库独立 try/except + 短超时，任何一个失败不影响其它库探测；
- TCP 层先探（<2s），通了再做真实协议握手，避免 /health 被慢库拖住；
- 结果跟随 .env 当前指向（本地或云端配置均可如实反映）。
"""

from __future__ import annotations

import socket
import time
from typing import Any

from app.core.config import get_settings
from app.utils.logger import logger


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _wrap_latency(detail: dict[str, Any], started: float) -> dict[str, Any]:
    detail.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 1))
    return detail


def mysql_health() -> dict[str, Any]:
    settings = get_settings()
    result: dict[str, Any] = {"status": "down"}
    started = time.perf_counter()
    host, port = settings.MYSQL_HOST, settings.MYSQL_PORT
    if not _tcp_open(host, port):
        return _wrap_latency(result | {"detail": f"TCP 不可达 {host}:{port}"}, started)
    try:
        import pymysql

        conn = pymysql.connect(
            host=host,
            port=port,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            database=settings.MYSQL_DB,
            connect_timeout=2,
            read_timeout=2,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION()")
                version = cur.fetchone()[0]
        finally:
            conn.close()
        result["status"] = "up"
        result["version"] = str(version)
    except Exception as exc:  # noqa: BLE001
        result["detail"] = f"{type(exc).__name__}: {exc}"
        logger.warning("MySQL 健康检查失败：%s", exc)
    return _wrap_latency(result, started)


def milvus_health() -> dict[str, Any]:
    settings = get_settings()
    result: dict[str, Any] = {"status": "down"}
    started = time.perf_counter()
    host, port = settings.MILVUS_HOST, settings.MILVUS_PORT
    if not _tcp_open(host, port):
        return _wrap_latency(result | {"detail": f"TCP 不可达 {host}:{port}"}, started)
    try:
        from pymilvus import MilvusClient  # 与 vector_store.py 一致的 3.x 风格

        uri_host = host if host.startswith(("http://", "https://")) else f"http://{host}"
        client = MilvusClient(uri=f"{uri_host}:{port}", db_name=settings.MILVUS_DB_NAME)
        # list_collections 成功即证明服务与鉴权可用
        client.list_collections()
        result["status"] = "up"
    except Exception as exc:  # noqa: BLE001
        result["detail"] = f"{type(exc).__name__}: {exc}"
        logger.warning("Milvus 健康检查失败：%s", exc)
    return _wrap_latency(result, started)


def redis_health() -> dict[str, Any]:
    from app.core.redis_client import get_redis_service

    service = get_redis_service()
    started = time.perf_counter()
    result: dict[str, Any] = {
        "enabled": service.enabled,
        "status": "down",
    }
    if not service.enabled:
        result["detail"] = "REDIS_ENABLED=false（可选增强按需降级）"
        return result
    try:
        ok = service.ping()
        result["status"] = "up" if ok else "down"
        if not ok:
            result["detail"] = "PING 未返回 PONG"
    except Exception as exc:  # noqa: BLE001
        result["detail"] = f"{type(exc).__name__}: {exc}"
    return _wrap_latency(result, started)


def neo4j_health() -> dict[str, Any]:
    from app.utils.neo4j_client import get_neo4j_service

    return get_neo4j_service().check_health()


def pgsql_health() -> dict[str, Any]:
    from app.db.analytics_session import ping_sync

    return ping_sync()


def run_all() -> dict[str, Any]:
    """返回五库状态聚合；overall 仅依赖核心三库(MySQL/Milvus/Neo4j/PgSQL)，Redis 可降级。"""
    checks = {
        "mysql": mysql_health(),
        "milvus": milvus_health(),
        "redis": redis_health(),
        "neo4j": neo4j_health(),
        "pgsql": pgsql_health(),
    }
    core_up = [
        checks[key]["status"] == "up"
        for key in ("mysql", "milvus", "neo4j", "pgsql")
    ]
    overall = "ok" if all(core_up) else "degraded"
    return {"status": overall, "checks": checks}
