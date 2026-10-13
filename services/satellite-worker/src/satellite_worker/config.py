
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
