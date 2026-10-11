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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
