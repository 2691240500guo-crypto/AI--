from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# SQLite 需 check_same_thread=False 以配合 FastAPI 多线程
# 袁文武 2026-09-02：MySQL 增加 connect_timeout 避免远程网络波动导致启动直接崩溃
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
elif "pymysql" in settings.DATABASE_URL or "mysql" in settings.DATABASE_URL:
    connect_args = {"connect_timeout": 10, "read_timeout": 30, "write_timeout": 30}
else:
    connect_args = {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    pool_recycle=3600,  # 连接回收时间（小时），避免长连接被服务端断开
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()