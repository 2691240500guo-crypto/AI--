"""安全验收当前 Redis：创建带 TTL 的临时键，验证后立即删除。"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.redis_client import get_redis_service


def main() -> int:
    settings = get_settings()
    if not settings.REDIS_ENABLED:
        print("FAIL: REDIS_ENABLED=false，请先在本机 .env 启用 Redis。")
        return 1

    parsed = urlsplit(settings.REDIS_URL)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        print("FAIL: REDIS_URL 格式无效，应为 redis:// 或 rediss:// 连接串。")
        return 1

    service = get_redis_service()
    if not service.ping():
        print("FAIL: Redis 无法连接，请检查服务状态、地址、端口和密码。")
        return 2

    key = f"connection-check:{uuid4().hex}"
    payload = {"project": "ai_talent", "purpose": "connection-check"}
    try:
        if not service.set_json(key, payload, ttl=60):
            print("FAIL: PING 成功，但临时键写入失败。")
            return 3
        if service.get_json(key) != payload:
            print("FAIL: 临时键读取结果不一致。")
            return 4
    finally:
        service.delete(key)
        service.close()

    print(f"PASS: Redis 连通且可读写（{parsed.hostname}:{parsed.port or 6379}）。")
    print(f"PASS: 键前缀为 {settings.REDIS_KEY_PREFIX!r}，临时验收键已删除。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
