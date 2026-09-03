# Redis 接入与团队使用说明

## 定位

Redis 是可选增强层，负责统计缓存、接口限流、JWT 注销黑名单和短时分布式锁。
MySQL 仍是唯一业务数据源；Redis 不可用时，人才、测评和培训主流程必须继续运行。

当前不缓存手机号、邮箱、简历、测评答案、报告全文和权限响应，也不使用 Redis
替代培训 outbox、消息记录或其他持久化数据。

## 团队配置

当前团队统一使用本机 Redis，云端 MySQL 配置保持不变。每位成员需要在自己的电脑上运行
Redis 服务，并安装项目使用的 `redis-py` Python 客户端。

1. 使用 Docker 启动仅供本机访问的 Redis 7：

```powershell
docker run -d --name ai-talent-redis -p 127.0.0.1:6379:6379 redis:7-alpine
```

   已经安装本机 Redis 服务的成员不需要再创建容器，只要确保 `localhost:6379` 可用。
2. 执行 `pip install -r requirements.txt` 安装 Python 依赖。
3. 在个人 `.env` 中配置：

```dotenv
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
REDIS_KEY_PREFIX=ai_talent:dev:<成员名>
```

4. 从项目根目录执行 `python scripts/verify_redis.py`。脚本只创建一个 60 秒 TTL
   的临时键，验证读写后立即删除。
5. 启动后端并访问 `/health`，确认 `enabled=true`、`available=true`。

Redis 端口只监听本机，不要映射到公网。个人环境不要在 Redis 中保存业务持久数据；即使
本机 Redis 被停止，核心业务也会自动回源云端 MySQL。

## 团队成员日常操作

每位成员拉取代码后执行：

```powershell
pip install -r requirements.txt
```

然后启动自己的 Redis 服务，在 `.env` 中保留团队云端 MySQL 配置，并加入上面的本机
Redis 三项配置。每位成员使用自己的 `REDIS_KEY_PREFIX`，再运行：

```powershell
docker start ai-talent-redis
python scripts/verify_redis.py
python -m pytest tests/test_redis_features.py -q
```

日常启动方式不变。出现连接问题时先看 `/health`；`available=false` 表示当前进程最近一次
Redis 操作失败，业务会回源 MySQL。先检查本机 Redis 服务是否启动，不要通过清空数据库来排障。

## 已接入能力

- 统计看板：overview/trend 缓存 10 分钟，distribution 缓存 30 分钟；相关写请求成功后立即失效。
- 登录态加速：当前用户、角色和权限快照缓存 30 分钟，避免每个请求重复访问云端 MySQL；相关管理接口写入后立即失效。
- 菜单加速：每个用户的菜单与权限码缓存 1 小时，硬刷新时与用户信息并行恢复。
- 首页加速：最近测评、岗位数量和培训概览缓存 1 分钟；消息按用户缓存 15 秒。
- 写后失效：人才、测评、培训、匹配、部门写请求成功后切换统计缓存版本。
- 权限失效：用户、角色或菜单写请求成功后立即切换登录态和菜单缓存版本。
- 登录限流：管理端与员工端按 IP + 用户名计数，成功登录后清零。
- AI 限流：NL2SQL 和测评报告按用户限流。
- JWT：新 Token 带 `jti`；退出和 Refresh Token 轮换时写入黑名单。
- 报告锁：多实例同时生成同一测评报告时只允许一个实例执行。

## 降级行为

- 缓存失败：直接查询 MySQL。
- 限流服务失败：请求放行并记录一次警告。
- 黑名单服务失败：保持现有无状态 JWT 行为。
- 分布式锁失败：请求放行，继续依靠 MySQL 事务和唯一约束。
- `/health` 返回 Redis 的 enabled/available/required 状态，其中 required 恒为 false。

## 验证

```powershell
python -m pytest tests/test_redis_features.py -q

$env:REDIS_ENABLED='true'
python -c "from app.core.redis_client import get_redis_service; assert get_redis_service().ping()"
```

还应完成：PING、两次看板请求命中缓存、写请求后版本变化、登录限流、退出后旧 Access Token
被拒绝，以及关闭本机 Redis 后看板自动回源 MySQL。
