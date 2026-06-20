from __future__ import annotations

from typing import Any

from app.services.sources.api_football import ApiFootballAdapter
from app.services.sources.espn import ESPNScoreboardAdapter
from app.services.sources.feature_sources import (
    FifaRankingSourceAdapter,
    GdeltNewsAdapter,
    OpenMeteoWeatherAdapter,
    StatsBombOpenDataAdapter,
)
from app.services.sources.football_data import FootballDataAdapter
from app.services.sources.humhub import HumHubFWC2026Adapter
from app.services.sources.openfootball import OpenFootballWorldCupAdapter
from app.services.sources.sportsdataio import SportsDataIOAdapter
from app.services.sources.thesportsdb import TheSportsDBAdapter
from app.services.sources.thestatsapi import TheStatsApiAdapter
from app.services.sources.tournamental_bot_arena import TournamentalBotArenaAdapter
from app.services.sources.tournamental_odds import TournamentalOddsAdapter
from app.services.sources.tournamental_wc2026 import TournamentalWC2026Adapter
from app.services.sources.worldcup_2026_api import WorldCup2026ApiAdapter
from app.services.sources.zafronix import ZafronixWorldCupAdapter


FIXTURE_ADAPTER_CLASSES = [
    FootballDataAdapter,
    ApiFootballAdapter,
    TheStatsApiAdapter,
    SportsDataIOAdapter,
    WorldCup2026ApiAdapter,
    TournamentalWC2026Adapter,
    ZafronixWorldCupAdapter,
    TheSportsDBAdapter,
    OpenFootballWorldCupAdapter,
    ESPNScoreboardAdapter,
    HumHubFWC2026Adapter,
]

FEATURE_AND_BENCHMARK_ADAPTER_CLASSES = [
    FifaRankingSourceAdapter,
    OpenMeteoWeatherAdapter,
    GdeltNewsAdapter,
    StatsBombOpenDataAdapter,
    TournamentalBotArenaAdapter,
    TournamentalOddsAdapter,
]

ALL_ADAPTER_CLASSES = FIXTURE_ADAPTER_CLASSES + FEATURE_AND_BENCHMARK_ADAPTER_CLASSES


def build_source_adapters(settings: Any, timeout_seconds: int = 12):
    return [adapter_cls(settings, timeout_seconds=timeout_seconds) for adapter_cls in ALL_ADAPTER_CLASSES]
