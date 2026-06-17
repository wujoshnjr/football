from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.services.source_fusion_service import SourceFusionService


EXPECTED_SOURCE_KEYS = {
    "zafronix_worldcup",
    "football_data",
    "api_football",
    "the_odds_api",
    "worldcup_2026_api",
    "statsbomb_open_data",
    "openfootball_worldcup_json",
    "openfootball_worldcup_text",
    "espn_scoreboard",
    "humhub_fwc_2026",
    "soccerdata_package",
    "github_football_scrapers",
}


def test_source_registry_contains_required_sources() -> None:
    registry = SourceFusionService(get_settings()).registry()
    keys = {source.key for source in registry}
    assert EXPECTED_SOURCE_KEYS.issubset(keys)


def test_source_registry_uses_english_public_text() -> None:
    registry = SourceFusionService(get_settings()).registry()
    combined = "\n".join(f"{source.role}\n{source.notes}" for source in registry)
    assert "資料" not in combined
    assert "賽程" not in combined
    assert "亂碼" not in combined


def test_source_context_is_stable() -> None:
    context = SourceFusionService(get_settings()).build_source_context()
    assert 0 <= context.reliability_score <= 1
    assert 0 <= context.fixture_consensus_score <= 1
    assert isinstance(context.sources_used, list)
    assert isinstance(context.sources_configured, list)
    assert isinstance(context.sources_missing, list)
