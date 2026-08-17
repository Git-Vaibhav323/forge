import shared.load_env  # noqa: F401 — must run before Settings()
from app.config import settings as shared_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = shared_settings.database_url
    llm_provider: str = shared_settings.llm_provider
    llm_api_key: str | None = shared_settings.llm_api_key
    llm_model: str | None = shared_settings.llm_model


settings = Settings()
settings.database_url = shared_settings.database_url
settings.llm_provider = shared_settings.llm_provider
settings.llm_api_key = shared_settings.llm_api_key
settings.llm_model = shared_settings.llm_model
