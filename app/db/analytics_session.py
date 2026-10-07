"""PgSQL 分析库会话（asyncpg）：只读分析链路专用。

M0 落位：独立容器 ai_pgsql（postgres:16-alpine，宿主 5433，库 ai_talent_analytics）。
设计边界：
- 业务写入仍在 MySQL（主数据源），本模块只服务\"分析/问数\"只读场景（M5 决策闭环接入）；
- 每次调用现连现断（分析低频 + 无池化依赖），超时短，避免拖累主线程；
- 提供 async 原生接口；同步场景（如 /health 的 def 路由）通过 run_in_sync 包装。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import asyncpg

from app.core.config import get_settings
from app.utils.logger import logger


async def _connect() -> asyncpg.Connection:
    settings = get_settings()
    return await asyncpg.connect(
        settings.PGSQL_URL,
        timeout=settings.PGSQL_CONNECT_TIMEOUT,
        command_timeout=5,
    )


async def ping_async() -> dict[str, Any]:
    """连通性自检（供 /health 与运维脚本使用）。"""
    result: dict[str, Any] = {"enabled": True, "status": "down"}
    settings = get_settings()
    if not settings.PGSQL_URL:
        result.update(enabled=False, detail="PGSQL_URL 未配置")
        return result
    started = time.perf_counter()
    conn = None
    try:
        conn = await _connect()
        version = await conn.fetchval("SELECT version()")
        result["status"] = "up"
        result["version"] = str(version).split(",")[0]
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    except Exception as exc:  # noqa: BLE001 asyncpg 异常种类多，统一降级
        result["status"] = "down"
        result["detail"] = f"{type(exc).__name__}: {exc}"
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result
    finally:
        if conn is not None:
            await conn.close()


async def fetch_all(query: str, *args: Any) -> list[dict[str, Any]]:
    """执行只读查询并返回 dict 列表；失败返回空列表（不抛到业务方）。"""
    conn = None
    try:
        conn = await _connect()
        rows = await conn.fetch(query, *args)
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        logger.warning("PgSQL 查询失败（降级处理）：%s", exc)
        return []
    finally:
        if conn is not None:
            await conn.close()


async def fetch_one(query: str, *args: Any) -> dict[str, Any] | None:
    conn = None
    try:
        conn = await _connect()
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("PgSQL 查询失败（降级处理）：%s", exc)
        return None
    finally:
        if conn is not None:
            await conn.close()


def ping_sync() -> dict[str, Any]:
    """同步场景（FastAPI def 路由/脚本）下的连通性自检。"""
    try:
        asyncio.get_running_loop()
        # 已在事件循环内：交给调用方走 async 版本，这里返回降级标记
        return {"status": "skip", "detail": "已在事件循环内，请调用 ping_async"}
    except RuntimeError:
        return asyncio.run(ping_async())
