
from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    database_url: str

    satellite_output_dir: Path = Path(
        "./data/satellite"
    )

    satellite_storage_backend: str = "local"

    gcs_bucket_name: str | None = None

    gcs_project_id: str | None = None

    gcs_credentials_path: Path | None = None

    satellite_delete_local_after_upload: bool = True

    earth_search_url: str = (
        "https://earth-search.aws.element84.com/v1"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
