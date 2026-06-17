from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Football World Cup Prediction Platform"
    app_env: str = "development"

    zafronix_worldcup_base_url: str | None = None
    zafronix_worldcup_key: str | None = None

    api_football_base_url: str = "https://v3.football.api-sports.io"
    api_football_key: str | None = None

    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_token: str | None = None

    worldcup_2026_public_base_url: str | None = None
    humhub_fwc_2026_base_url: str | None = None

    database_url: str | None = None
    redis_url: str | None = None
    model_version: str = "wc-mvp-v0.2.0-source-aware"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
