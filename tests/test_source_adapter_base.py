from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.sources.api_football import ApiFootballAdapter
from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url, redact_url
from app.services.sources.feature_sources import OpenMeteoWeatherAdapter
from app.services.sources.tournamental_bot_arena import TournamentalBotArenaAdapter


def test_source_adapter_result_hides_records_by_default() -> None:
    result = SourceAdapterResult(
        source_key="demo",
        attempted=True,
        configured=True,
        enabled=True,
        ok=True,
        status="ok",
        records=[{"secret": "not for report"}],
        record_count=1,
    )

    report = result.to_report_dict()

    assert report["source_key"] == "demo"
    assert report["records"] == []
    assert result.to_report_dict(include_records=True)["records"] == [{"secret": "not for report"}]


def test_redact_url_removes_sensitive_values() -> None:
    url = "https://example.test/path?api_key=abc&token=def&normal=value"

    assert redact_url(url) == "https://example.test/path?api_key=REDACTED&token=REDACTED&normal=value"


def test_build_url_handles_path_and_params() -> None:
    assert build_url("https://api.example.test/v1/", "/fixtures", {"season": 2026}) == "https://api.example.test/v1/fixtures?season=2026"


def test_api_football_missing_key_does_not_crash() -> None:
    settings = SimpleNamespace(
        api_football_base_url="https://v3.football.api-sports.io",
        api_football_key=None,
        api_football_enabled=True,
        api_football_worldcup_league_id=1,
        api_football_worldcup_season=2026,
    )

    result = asyncio.run(ApiFootballAdapter(settings).fetch())

    assert result.source_key == "api_football"
    assert result.status == "missing_credentials"
    assert not result.ok
    assert not result.attempted


def test_open_meteo_feature_source_ready_without_creating_fixtures() -> None:
    settings = SimpleNamespace(
        open_meteo_enabled=True,
        open_meteo_base_url="https://api.open-meteo.com/v1",
        open_meteo_archive_base_url="https://archive-api.open-meteo.com/v1",
    )

    adapter = OpenMeteoWeatherAdapter(settings)
    result = asyncio.run(adapter.fetch())

    assert adapter.produces_fixtures is False
    assert result.ok
    assert result.record_count == 0
    assert result.status == "weather_feature_source_not_fixture_ingestion"


def test_tournamental_bot_arena_is_read_only_even_when_submission_flag_exists() -> None:
    settings = SimpleNamespace(
        tournamental_enabled=True,
        tournamental_enable_read_only_feeds=True,
        tournamental_enable_pick_submission=True,
        tournamental_base_url="https://play.tournamental.com",
        tournamental_api_key="tnm_secret",
        tournamental_tournament_id="fifa-wc-2026",
        tournamental_bot_id="bot-1",
        tournamental_mode="bot_arena_benchmark",
    )

    adapter = TournamentalBotArenaAdapter(settings)
    result = asyncio.run(adapter.fetch())

    assert adapter.produces_fixtures is False
    assert result.ok
    assert result.status == "read_only_ready_pick_submission_not_used_by_ingestion"
    assert result.records[0]["safety_note"] == "adapter does not submit picks or trigger live betting"
