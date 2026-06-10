from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_name: str = "ddakkok-be"

    database_url: str = "postgresql+psycopg://ddakkok:ddakkok@db:5432/ddakkok"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    ai_provider: str = "mock"
    ocr_provider: str = "mock"

    clova_ocr_api_key: str = ""
    clova_ocr_api_url: str = ""

    ai_cache_enabled: bool = True
    ai_cache_maxsize: int = 256

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    gms_api_key: str = ""
    gms_api_url: str = ""
    gms_model: str = ""

    embedding_provider: str = "mock"  # mock | openai | gms
    openai_embedding_model: str = "text-embedding-3-small"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()