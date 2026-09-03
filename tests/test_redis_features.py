"""Redis 可选增强的独立回归测试，不依赖真实 Redis 服务。"""

from types import SimpleNamespace

from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.deps import (_user_perms, cache_authenticated_user,
                           load_authenticated_user)
from app.core.redis_client import RedisService, get_redis_service
from app.core.security import create_access_token, decode_token, is_token_revoked, revoke_token
from app.dao.user import UserDAO


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def ping(self):
        return True

    def close(self):
        return None

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = str(value)
        if ex is not None:
            self.ttls[key] = int(ex)
        return True

    def delete(self, key):
        existed = key in self.values
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return int(existed)

    def incr(self, key):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    def exists(self, key):
        return int(key in self.values)

    def eval(self, script, number_of_keys, key, *args):
        assert number_of_keys == 1
        if "redis.call('incr'" in script:
            count = self.incr(key)
            if count == 1:
                self.ttls[key] = int(args[0])
            return [count, self.ttls[key]]
        token = str(args[0])
        if self.values.get(key) == token:
            return self.delete(key)
        return 0


class BrokenRedis:
    def __getattr__(self, name):
        def unavailable(*args, **kwargs):
            raise RedisConnectionError("offline")

        return unavailable


def test_cache_hit_and_namespace_invalidation():
    fake = FakeRedis()
    service = RedisService(fake, enabled=True)
    assert not service.available
    assert service.ping()
    assert service.available
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return {"value": calls}

    assert service.cached_json("analytics", "overview", 60, loader) == {"value": 1}
    assert service.cached_json("analytics", "overview", 60, loader) == {"value": 1}
    assert calls == 1

    assert service.invalidate_namespace("analytics")
    assert service.cached_json("analytics", "overview", 60, loader) == {"value": 2}
    assert calls == 2


def test_rate_limit_hashes_identity_and_resets():
    fake = FakeRedis()
    service = RedisService(fake, enabled=True)
    identity = "127.0.0.1|private-user"

    assert service.rate_limit("login", identity, limit=2, window=30) == (True, 30)
    assert service.rate_limit("login", identity, limit=2, window=30) == (True, 30)
    assert service.rate_limit("login", identity, limit=2, window=30) == (False, 30)
    assert all("private-user" not in key for key in fake.values)
    assert service.clear_rate_limit("login", identity)
    assert service.rate_limit("login", identity, limit=2, window=30)[0]


def test_lock_is_mutually_exclusive_and_releases_safely():
    fake = FakeRedis()
    first = RedisService(fake, enabled=True)
    second = RedisService(fake, enabled=True)

    with first.lock("assessment-report:1", ttl=30) as first_acquired:
        assert first_acquired
        with second.lock("assessment-report:1", ttl=30) as second_acquired:
            assert not second_acquired
    with second.lock("assessment-report:1", ttl=30) as acquired_after_release:
        assert acquired_after_release


def test_jwt_blacklist_uses_remaining_token_ttl(monkeypatch):
    service = get_redis_service()
    fake = FakeRedis()
    monkeypatch.setattr(service, "_client", fake)
    monkeypatch.setattr(service, "_enabled_override", True)

    token = create_access_token("42")
    payload = decode_token(token)
    assert payload and payload.get("jti")
    assert not is_token_revoked(payload)
    assert revoke_token(token)
    assert is_token_revoked(payload)
    blacklist_keys = [key for key in fake.values if ":auth:blacklist:" in key]
    assert len(blacklist_keys) == 1
    assert fake.ttls[blacklist_keys[0]] > 0


def test_disabled_redis_always_uses_source_loader():
    service = RedisService(enabled=False)
    calls = 0

    def loader():
        nonlocal calls
        calls += 1
        return calls

    assert service.cached_json("analytics", "overview", 60, loader) == 1
    assert service.cached_json("analytics", "overview", 60, loader) == 2
    assert service.rate_limit("login", "someone", limit=1, window=30) == (True, 0)


def test_unavailable_redis_degrades_without_blocking_business_logic():
    service = RedisService(BrokenRedis(), enabled=True)
    assert not service.ping()
    assert not service.available
    assert service.cached_json("analytics", "overview", 60, lambda: {"source": "mysql"}) == {
        "source": "mysql"
    }
    assert service.rate_limit("login", "someone", limit=1, window=30) == (True, 0)
    with service.lock("assessment-report:1") as acquired:
        assert acquired


def test_authenticated_user_snapshot_skips_database(monkeypatch):
    service = get_redis_service()
    fake = FakeRedis()
    monkeypatch.setattr(service, "_client", fake)
    monkeypatch.setattr(service, "_enabled_override", True)

    menu = SimpleNamespace(
        id=7, parent_id=0, title="人才", icon=None, path="/talent",
        component="talent/index", perm="talent:list", type=2, sort=1,
        status=1, created_at=None,
    )
    role = SimpleNamespace(
        id=3, code="hr", name="HR", remark=None, status=1,
        created_at=None, menus=[menu],
    )
    user = SimpleNamespace(
        id=42, username="cached-user", nickname="缓存用户", phone=None,
        email=None, avatar=None, dept_id=None, status=1, is_super=0,
        openid=None, emp_no=None, talent_id=None, user_type="admin",
        last_login_at=None, created_at=None, updated_at=None, roles=[role],
    )
    cache_authenticated_user(user)

    def unexpected_db_call(*args, **kwargs):
        raise AssertionError("缓存命中时不应查询数据库")

    monkeypatch.setattr(UserDAO, "get", unexpected_db_call)
    cached = load_authenticated_user(object(), 42)
    assert cached.username == "cached-user"
    assert _user_perms(cached) == {"talent:list", "talent:*"}
