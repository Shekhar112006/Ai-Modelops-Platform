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
    recovery_claim_timeout_seconds: float = Field(default=300.0, gt=0)

    api_prefix: str = "/api/v1"
    dataset_storage_dir: str = "data/datasets"
    dataset_max_upload_bytes: int = Field(
        default=20 * 1024 * 1024,
        gt=0,
    )
    dataset_preview_max_rows: int = Field(
        default=100,
        ge=1,
        le=100,
    )

    mlflow_tracking_uri: str = "http://127.0.0.1:5000"
    model_server_url: str = "http://127.0.0.1:8003"
    prediction_timeout_seconds: float = Field(default=15.0, gt=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()