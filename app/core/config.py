from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Primmo FastAPI Template"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    uploads_dir: str = "data/uploads"
    graph_store_state_file: str = "data/graph_store_state.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
