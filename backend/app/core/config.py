from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 仓库根目录的 .env(backends/app/core/config.py 向上 4 级)
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE, env_file_encoding="utf-8", extra="ignore"
    )

    APP_NAME: str = "DocAgent"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # JWT
    SECRET_KEY: str = "dev-secret-change-me-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # PostgreSQL
    POSTGRES_USER: str = "docagent"
    POSTGRES_PASSWORD: str = "docagent_dev_password"
    POSTGRES_DB: str = "docagent"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # QDrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "docagent_knowledge"

    # 嵌入参数
    EMBEDDING_MODEL_DIM: int = 1024  # bge-m3
    EMBEDDING_BATCH_SIZE: int = 32

    # LLM / 嵌入 / 重排提供商(D3/D5 使用,先留空)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_CHAT_MODEL: str = "deepseek-v4-flash"
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
