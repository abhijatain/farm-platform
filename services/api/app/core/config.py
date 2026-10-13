from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    environment: str = "development"

    firebase_project_id: str

    firebase_credentials_path: Path | None = None
    dev_firebase_uid: str = "seed-dev-user"

    dev_phone_e164: str = "+919999999999"

    dev_user_name: str = "Seed Dev User"

    cors_origins: str = (
        "http://localhost:8081," "http://127.0.0.1:8081," "http://192.168.1.8:8081"
    )
    # -------------------------------------------------
    # OBJECT STORAGE
    # -------------------------------------------------

    storage_backend: str = "local"

    storage_local_root: Path = Path("./data/storage")

    gcs_bucket_name: str | None = None

    gcs_project_id: str | None = None

    gcs_credentials_path: Path | None = None

    media_upload_url_expiry_minutes: int = 15

    media_download_url_expiry_minutes: int = 30

    media_max_image_bytes: int = 25 * 1024 * 1024

    media_max_video_bytes: int = 500 * 1024 * 1024

    # -------------------------------------------------
    # MEDIA DERIVATIVES
    # -------------------------------------------------

    media_derivatives_enabled: bool = True

    media_thumbnail_max_pixels: int = 1200

    media_thumbnail_webp_quality: int = 82

    media_video_poster_max_pixels: int = 1280

    ffmpeg_binary: str = "ffmpeg"

    ffprobe_binary: str = "ffprobe"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
