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

    # 数据库地址必须由环境配置提供；本项目不再隐式回退到 SQLite。
    DATABASE_URL: str
    AUTO_INIT_DB: bool = False
    # ---- 云端 MySQL 连接参数（与 .env 的 MYSQL_* 对应）----
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "ai_talent"
    SECRET_KEY: str
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
    # ---- 硅基流动（SiliconFlow）统一配置 ----
    # 大模型统一走硅基流动：chat 用 Qwen3-30B-A3B、embedding 用 bge-m3
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICONFLOW_API_KEY: str = ""      # 与 SILICON_FLOW_API_KEY 二选一填写（.env）
    SILICONFLOW_MODEL: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    SILICONFLOW_TIMEOUT: int = 20

    # ============ C 测评报告配置 ============
    ASSESSMENT_REPORT_MODE: str = "siliconflow"
    ASSESSMENT_PASS_RATE: float = 0.60
    ASSESSMENT_WEAK_RATE: float = 0.60
    ASSESSMENT_AI_TIMEOUT: int = 20

    # ---- 硅基流动（SiliconFlow，OpenAI 兼容 API，统一默认走硅基流动）----
    # LLM_STRATEGY: "ollama" | "silicon_flow"，控制 chat/embed 走哪个后端
    LLM_STRATEGY: str = "silicon_flow"
    SILICON_FLOW_API_KEY: str = ""
    SILICON_FLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    SILICON_FLOW_LLM_MODEL: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    SILICON_FLOW_EMBED_MODEL: str = "BAAI/bge-m3"
    SILICON_FLOW_ASR_MODEL: str = "Qwen/Qwen3-Omni-30B-A3B-Instruct"
    SILICON_FLOW_TTS_MODEL: str = "FunAudioLLM/CosyVoice2-0.5B"
    SILICON_FLOW_TTS_VOICE: str = "FunAudioLLM/CosyVoice2-0.5B:claire"

    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_DB_NAME: str = "default"
    MILVUS_COLLECTION_PREFIX: str = "talent_"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_SECURE: bool = False
    MINIO_BUCKET: str = "ai-talent"


@lru_cache
def get_settings() -> Settings:
    return Settings()
