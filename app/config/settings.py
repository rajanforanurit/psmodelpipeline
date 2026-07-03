from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    google_service_account_json: str
    google_drive_folder_id: str
    qdrant_url: str
    qdrant_api_key: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
