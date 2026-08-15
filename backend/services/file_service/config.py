from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    database_url: str = "postgresql+psycopg://forgedata:forgedata@localhost:5433/forgedata"
    project_service_url: str = "http://localhost:8001"
    object_storage_endpoint: str = "localhost:9000"
    object_storage_access_key: str = "forgedata"
    object_storage_secret_key: str = "forgedata"
    object_storage_bucket: str = "forgedata"
    object_storage_secure: bool = False


settings = Settings()
