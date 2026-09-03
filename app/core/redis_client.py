"""Redis 可选增强：缓存、限流、Token 黑名单和短时分布式锁。

MySQL 始终是业务数据源。Redis 未启用或不可用时，除安全限流失去增强外，
所有调用都安全降级，不阻塞人才、测评和培训主流程。
"""

from __future__ import annotations

import hashlib
import json
import secrets
from contextlib import contextmanager
from threading import Lock
from typing import Any, Callable, Iterator, TypeVar

from redis import Redis
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import RedisError
from redis.retry import Retry

from app.core.config import get_settings
from app.utils.logger import logger


T = TypeVar("T")
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""
_RATE_LIMIT_SCRIPT = """
local current = redis.call('incr', KEYS[1])
if current == 1 then
  redis.call('expire', KEYS[1], ARGV[1])
end
local ttl = redis.call('ttl', KEYS[1])
return {current, ttl}
"""


class RedisService:
    """共享 redis-py 客户端；一个进程只创建一个连接池。"""

    def __init__(self, client: Redis | None = None, *, enabled: bool | None = None) -> None:
        self._client = client
        self._enabled_override = enabled
        self._create_lock = Lock()
        self._warned = False
        self._last_available = False

    @property
    def enabled(self) -> bool:
        if self._enabled_override is not None:
            return self._enabled_override
        return get_settings().REDIS_ENABLED

    @property
    def available(self) -> bool:
        """最近一次 Redis 操作状态；读取本属性不会触发网络请求。"""
        return self.enabled and self._last_available

    def _key(self, *parts: object) -> str:
        prefix = get_settings().REDIS_KEY_PREFIX.strip(":")
        suffix = ":".join(str(part).strip(":") for part in parts)
        return f"{prefix}:{suffix}" if suffix else prefix

    def _get_client(self) -> Redis | None:
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        with self._create_lock:
            if self._client is None:
                settings = get_settings()
                self._client = Redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    max_connections=settings.REDIS_MAX_CONNECTIONS,
                    socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT,
                    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
                    health_check_interval=settings.REDIS_HEALTH_CHECK_INTERVAL,
                    retry=Retry(
                        ExponentialWithJitterBackoff(cap=0.5, base=0.05),
                        settings.REDIS_RETRY_COUNT,
                    ),
                )
        return self._client

    def _safe(self, operation: Callable[[Redis], T], default: T) -> T:
        client = self._get_client()
        if client is None:
            return default
        try:
            value = operation(client)
            self._warned = False
            self._last_available = True
            return value
        except (RedisError, OSError, ConnectionError, TimeoutError) as exc:
            self._last_available = False
            if not self._warned:
                logger.warning("Redis 不可用，当前请求已降级：%s", type(exc).__name__)
                self._warned = True
            return default

    def ping(self) -> bool:
        return bool(self._safe(lambda client: client.ping(), False))

    def close(self) -> None:
        client = self._client
        self._client = None
        self._last_available = False
        if client is not None:
            try:
                client.close()
            except RedisError:
                pass

    def get_json(self, key: str) -> Any | None:
        raw = self._safe(lambda client: client.get(self._key(key)), None)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            self.delete(key)
            return None

    def set_json(self, key: str, value: Any, ttl: int) -> bool:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        return bool(self._safe(
            lambda client: client.set(self._key(key), payload, ex=max(1, ttl)),
            False,
        ))

    def delete(self, key: str) -> bool:
        return bool(self._safe(lambda client: client.delete(self._key(key)), 0))

    def namespace_version(self, namespace: str) -> int:
        key = self._key("cache-version", namespace)

        def load(client: Redis) -> int:
            value = client.get(key)
            if value is None:
                client.set(key, 1, nx=True)
                return 1
            return int(value)

        return int(self._safe(load, 1))

    def versioned_key(self, namespace: str, name: str) -> str:
        return f"cache:{namespace}:v{self.namespace_version(namespace)}:{name}"

    def invalidate_namespace(self, namespace: str) -> bool:
        key = self._key("cache-version", namespace)
        return bool(self._safe(lambda client: client.incr(key), 0))

    def cached_json(self, namespace: str, name: str, ttl: int, loader: Callable[[], T]) -> T:
        if not self.enabled:
            return loader()
        key = self.versioned_key(namespace, name)
        cached = self.get_json(key)
        if cached is not None:
            return cached
        value = loader()
        self.set_json(key, value, ttl)
        return value

    @staticmethod
    def _identity_digest(identity: str) -> str:
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]

    def rate_limit(self, scope: str, identity: str, *, limit: int, window: int) -> tuple[bool, int]:
        """返回 ``(是否允许, 剩余等待秒数)``；Redis 故障时放行。"""
        if not self.enabled:
            return True, 0
        key = self._key("rate", scope, self._identity_digest(identity))
        result = self._safe(
            lambda client: client.eval(_RATE_LIMIT_SCRIPT, 1, key, max(1, window)),
            None,
        )
        if not result:
            return True, 0
        current, ttl = int(result[0]), max(0, int(result[1]))
        return current <= max(1, limit), ttl

    def clear_rate_limit(self, scope: str, identity: str) -> bool:
        return bool(self._safe(
            lambda client: client.delete(
                self._key("rate", scope, self._identity_digest(identity))
            ),
            0,
        ))

    def blacklist_token(self, jti: str | None, ttl: int) -> bool:
        if not jti or ttl <= 0:
            return False
        return bool(self._safe(
            lambda client: client.set(self._key("auth", "blacklist", jti), "1", ex=ttl),
            False,
        ))

    def is_token_blacklisted(self, jti: str | None) -> bool:
        if not jti:
            return False
        return bool(self._safe(
            lambda client: client.exists(self._key("auth", "blacklist", jti)),
            0,
        ))

    @contextmanager
    def lock(self, name: str, *, ttl: int | None = None) -> Iterator[bool]:
        """短时互斥锁。Redis 故障时降级放行，MySQL 约束仍是最终防线。"""
        if not self.enabled:
            yield True
            return
        key = self._key("lock", name)
        token = secrets.token_hex(16)
        lock_ttl = ttl or get_settings().REDIS_LOCK_TTL
        acquired = bool(self._safe(
            lambda client: client.set(key, token, nx=True, ex=max(1, lock_ttl)),
            True,
        ))
        try:
            yield acquired
        finally:
            if acquired:
                self._safe(
                    lambda client: client.eval(_RELEASE_LOCK_SCRIPT, 1, key, token),
                    0,
                )


_redis_service = RedisService()


def get_redis_service() -> RedisService:
    return _redis_service


def enforce_rate_limit(scope: str, identity: str, *, limit: int, window: int) -> None:
    """统一限流入口，沿用项目的业务错误响应格式。"""
    allowed, retry_after = _redis_service.rate_limit(
        scope,
        identity,
        limit=limit,
        window=window,
    )
    if not allowed:
        from app.utils.response import BusinessError

        raise BusinessError(429, f"请求过于频繁，请在 {retry_after or window} 秒后重试")
