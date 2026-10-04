from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    environment: str = "development"

    # Temporary development identity.
    # Firebase authentication will replace this later.
    dev_firebase_uid: str = "dev-local-user"
    dev_phone_e164: str = "+910000000001"
    dev_user_name: str = "Development User"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
