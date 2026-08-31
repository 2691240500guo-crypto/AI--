from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根目录（本文件位于 <root>/app/core/config.py，向上 3 层）
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# .env 固定用绝对路径：无论从哪个目录启动都能读到（避免回退到默认 SQLite）
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """应用配置，从 .env 读取。"""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "AI Talent Platform"
    VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./dev.db"
    # ---- 云端 MySQL 连接参数（与 .env 的 MYSQL_* 对应）----
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "ai_talent"
    SECRET_KEY: str = "dev-secret-change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:8080"
    REDIS_URL: str = "redis://localhost:6379/0"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ============ AI 基建配置 ============
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    OLLAMA_TIMEOUT: int = 120

    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_DB_NAME: str = "default"
    MILVUS_COLLECTION_PREFIX: str = "talent_"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "ai-talent"


@lru_cache
def get_settings() -> Settings:
    return Settings()