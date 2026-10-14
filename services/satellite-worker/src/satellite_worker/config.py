
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    database_url: str

    earth_search_url: str = (
        "https://earth-search.aws.element84.com/v1"
    )

    gcs_bucket_name: str

    gcs_project_id: str | None = None

    gcs_credentials_path: Path | None = None

    # Automatic ingestion orchestration.
    satellite_job_poll_seconds: float = 15.0

    satellite_incremental_enqueue_interval_minutes: int = 60

    satellite_incremental_lookback_days: int = 14

    satellite_job_retry_delay_minutes: int = 15

    satellite_job_stale_after_minutes: int = 720

    satellite_job_max_attempts: int = 3

    satellite_max_scene_cloud: float = 60.0

    satellite_scene_limit: int = 20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
