"""Neo4j 知识图谱客户端：连通性自检 + 统一执行入口。

M0 落位：人才-技能-岗位-测评-培训 关系网络的地基（M1~M4 逐个里程碑接入）。
设计原则与 redis_client.py 一致：
- 惰性创建 driver，首次使用时才建立连接，导入模块不产生副作用；
- 图谱不可用时所有调用安全降级（返回空/False），不阻塞人才/测评/培训主流程；
- 写入路径统一走本模块的 execute_query，方便后续加审计与幂等。
"""

from __future__ import annotations

import time
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from app.core.config import get_settings
from app.utils.logger import logger


class Neo4jService:
    """共享 neo4j driver；一个进程只创建一个 driver（连接池由驱动管理）。"""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self._driver = None
        self._enabled_override = enabled
        self._last_available = False

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        settings = get_settings()
        return bool(settings.NEO4J_URI and settings.NEO4J_PASSWORD)

    def _get_driver(self):
        """惰性创建 driver；失败仅告警，不抛到业务调用方。"""
        if not self.enabled:
            return None
        if self._driver is None:
            settings = get_settings()
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
                connection_timeout=settings.NEO4J_CONNECT_TIMEOUT,
                max_connection_lifetime=3600,
            )
        return self._driver

    def close(self) -> None:
        driver = self._driver
        self._driver = None
        self._last_available = False
        if driver is not None:
            try:
                driver.close()
            except Neo4jError:
                pass

    def ping(self) -> bool:
        """连通性自检：驱动握手 + RETURN 1。"""
        driver = self._get_driver()
        if driver is None:
            return False
        try:
            with driver.session() as session:
                record = session.run("RETURN 1 AS ok").single()
                ok = bool(record and record["ok"] == 1)
            self._last_available = ok
            return ok
        except Exception as exc:  # noqa: BLE001 驱动异常种类多，统一降级
            self._last_available = False
            logger.warning("Neo4j 不可用（降级处理）：%s: %s", type(exc).__name__, exc)
            return False

    @property
    def available(self) -> bool:
        return self.enabled and self._last_available

    def execute_query(self, cypher: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """统一执行入口：跑 Cypher 并返回 record 列表（dict 化）。

        图谱不可用时返回空列表，调用方按\"无关系数据\"处理即可。
        """
        driver = self._get_driver()
        if driver is None:
            return []
        try:
            with driver.session() as session:
                records = session.run(cypher, params or {}).data()
            self._last_available = True
            return records
        except Exception as exc:  # noqa: BLE001
            self._last_available = False
            logger.warning("Neo4j 查询失败（降级处理）：%s", exc)
            return []

    def execute_transaction(self, tx_fn, default: Any = None) -> Any:
        """事务式统一执行入口：多条写入语句在一个事务内原子提交。

        :param tx_fn: 接收 ``tx`` 的可调用对象（内部逐条 tx.run(...)）。
        :param default: Neo4j 不可用/异常时返回的降级值（默认 None）。
        供批量写图（kg_sync）使用；读场景请用 execute_query。
        """
        driver = self._get_driver()
        if driver is None:
            return default
        try:
            with driver.session() as session:
                result = session.execute_write(tx_fn)
            self._last_available = True
            return result
        except Exception as exc:  # noqa: BLE001
            self._last_available = False
            logger.warning("Neo4j 事务失败（降级处理）：%s", exc)
            return default

    def check_health(self) -> dict[str, Any]:
        """供 /health 自检面板使用的结构化状态。"""
        started = time.perf_counter()
        result: dict[str, Any] = {"enabled": self.enabled, "status": "down"}
        if not self.enabled:
            result["detail"] = "NEO4J_URI 未配置"
            result["latency_ms"] = 0
            return result
        driver = self._get_driver()
        if driver is None:
            result["detail"] = "driver 创建失败"
            result["latency_ms"] = 0
            return result
        try:
            with driver.session() as session:
                record = session.run("RETURN 1 AS ok").single()
                ok = bool(record and record["ok"] == 1)
            result["status"] = "up" if ok else "down"
            self._last_available = ok
            if not ok:
                result["detail"] = "RETURN 1 未返回预期值"
        except Exception as exc:  # noqa: BLE001
            self._last_available = False
            result["status"] = "down"
            result["detail"] = f"{type(exc).__name__}: {exc}"
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        return result


_neo4j_service = Neo4jService()


def get_neo4j_service() -> Neo4jService:
    return _neo4j_service
