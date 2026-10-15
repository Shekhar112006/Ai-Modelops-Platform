from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "AI ModelOps Platform"
    environment: str = "development"

    database_url: str
    redis_url: str
    celery_result_backend: str
    health_check_timeout_seconds: float = 5.0
    health_check_interval_seconds: float = 60.0
    health_check_failure_threshold: int = Field(default=3, ge=1)

    api_prefix: str = "/api/v1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()