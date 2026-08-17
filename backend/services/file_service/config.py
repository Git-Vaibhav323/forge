import shared.load_env  # noqa: F401 — must run before Settings()
from app.config import settings as shared_settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = shared_settings.database_url
    project_service_url: str = "http://localhost:8001"
    object_storage_endpoint: str = "localhost:9000"
    object_storage_access_key: str = "forgedata"
    object_storage_secret_key: str = "forgedata"
    object_storage_bucket: str = "forgedata"
    object_storage_secure: bool = False
    object_storage_region: str = "us-east-1"

    # Web page ingest (URL → stored document). Leave Apify/custom empty until needed.
    web_fetch_provider: str = "direct"  # direct | apify | custom
    apify_api_token: str | None = None
    apify_actor_id: str | None = None
    web_fetch_api_url: str | None = None
    web_fetch_api_key: str | None = None


settings = Settings()
settings.database_url = shared_settings.database_url
