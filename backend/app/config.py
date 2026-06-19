from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Football World Cup Prediction Platform"
    app_env: str = "development"

    zafronix_worldcup_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ZAFRONIX_WORLDCUP_BASE_URL",
            "ZAFRONIX_WORLD_CUP_BASE_URL",
            "zafronix_worldcup_base_url",
        ),
    )
    zafronix_worldcup_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ZAFRONIX_WORLDCUP_KEY",
            "ZAFRONIX_WORLD_CUP_API_KEY",
            "ZAFRONIX_WORLD_CUP_KEY",
            "zafronix_worldcup_key",
        ),
    )
    zafronix_worldcup_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "ZAFRONIX_WORLD_CUP_ENABLED",
            "ZAFRONIX_WORLDCUP_ENABLED",
            "zafronix_worldcup_enabled",
        ),
    )

    api_football_base_url: str = "https://v3.football.api-sports.io"
    api_football_key: str | None = None
    api_football_worldcup_league_id: int = 1
    api_football_worldcup_season: int = 2026
    api_football_enabled: bool = True

    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_token: str | None = None
    football_data_worldcup_competition_code: str = "WC"
    football_data_enabled: bool = True

    tournamental_api_key: str | None = None
    tournamental_base_url: str | None = None
    tournamental_odds_base_url: str = "https://odds.tournamental.com"
    tournamental_odds_enabled: bool = False
    tournamental_wc2026_base_url: str = Field(
        default="https://wc2026.tournamental.com",
        validation_alias=AliasChoices(
            "TOURNAMENTAL_WC2026_BASE_URL",
            "tournamental_wc2026_base_url",
        ),
    )
    tournamental_wc2026_enabled: bool = True

    worldcup_2026_public_base_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "WORLD_CUP_2026_API_BASE_URL",
            "WORLDCUP_2026_PUBLIC_BASE_URL",
            "worldcup_2026_public_base_url",
        ),
    )
    worldcup_2026_api_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "WORLD_CUP_2026_API_ENABLED",
            "WORLDCUP_2026_PUBLIC_ENABLED",
            "worldcup_2026_api_enabled",
        ),
    )

    thestatsapi_base_url: str = "https://api.thestatsapi.com/api"
    thestatsapi_key: str | None = None
    thestatsapi_enabled: bool = False
    thestatsapi_world_cup_competition_id: str | None = None
    thestatsapi_world_cup_season_id: str | None = None

    sportsdataio_base_url: str = "https://api.sportsdata.io/v3/soccer"
    sportsdataio_api_key: str | None = None
    sportsdataio_enabled: bool = False
    sportsdataio_mode: str = "trial_evaluation_only"
    sportsdataio_world_cup_competition_key: str | None = None
    sportsdataio_world_cup_season: str = "2026"
    sportsdataio_world_cup_fixtures_path: str = "/scores/json/GamesByCompetition/{competition_key}/{season}"

    thesportsdb_base_url: str = "https://www.thesportsdb.com/api/v1/json"
    thesportsdb_api_key: str = "123"
    thesportsdb_enabled: bool = False
    thesportsdb_world_cup_league_id: str = "4429"
    thesportsdb_world_cup_season: str = "2026"

    humhub_fwc_2026_base_url: str | None = None
    humhub_fwc_2026_enabled: bool = False

    openfootball_worldcup_json_url: str = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
    statsbomb_open_data_base_url: str = "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
    espn_scoreboard_url: str = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
    soccerdata_project_url: str = "https://github.com/probberechts/soccerdata"

    database_url: str | None = None
    redis_url: str | None = None
    model_version: str = "wc-mvp-v0.2.0-source-aware"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
