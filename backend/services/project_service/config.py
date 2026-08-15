import shared.load_env  # noqa: F401 — must run before Settings()
from app.config import settings as shared_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = shared_settings.database_url
    postgres_host: str | None = None
    postgres_password: str | None = None


settings = Settings()
settings.database_url = shared_settings.database_url
