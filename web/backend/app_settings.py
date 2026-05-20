from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+psycopg://vitrine:vitrine@localhost:5432/vitrine")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    etl_trigger_token: str = Field(default="dev-token-change-me")
    etl_threads: int = Field(default=10)
    etl_periodo_granularidade: str = Field(default="MENSAL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
