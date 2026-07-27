from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "digit-catalog-analyzer"
    database_url: str = "postgresql+psycopg://catalog:catalog@localhost:5432/catalog"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://catalog:catalog@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"
    external_api_base_url: str = ""
    candidate_id: str = ""
    request_timeout_seconds: int = Field(default=30, ge=1)
    max_download_batch_size: int = Field(default=3, ge=1, le=3)


@lru_cache
def get_settings() -> Settings:
    return Settings()
