"""Validate storage and COG serving configuration for TiTiler."""

from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    gcs_project_id: str | None = None

    gcs_bucket_name: str

    gcs_credentials_path: Path | None = None

    # Used internally by TiTiler/GDAL for private HTTP range reads.
    gcs_read_url_expiry_minutes: int = 15

    cors_origins: str = (
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
