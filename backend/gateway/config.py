from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"
    project_service_url: str = "http://localhost:8001"
    file_service_url: str = "http://localhost:8002"


settings = Settings()
