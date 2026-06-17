from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pytest

from app.services.odds_api_client import OddsApiClient, OddsApiError


def test_odds_api_client_reports_missing_key() -> None:
    settings = SimpleNamespace(
        the_odds_api_base_url="https://api.the-odds-api.com/v4",
        the_odds_api_key=None,
        the_odds_api_regions="eu,uk,us",
        the_odds_api_markets="h2h",
        the_odds_api_odds_format="decimal",
        the_odds_api_sport_key="upcoming",
    )
    client = OddsApiClient(settings)
    assert client.configured is False
    with pytest.raises(OddsApiError):
        client.odds()


def test_odds_api_client_builds_safe_v4_urls() -> None:
    settings = SimpleNamespace(
        the_odds_api_base_url="https://api.the-odds-api.com/v4",
        the_odds_api_key="test-key",
        the_odds_api_regions="eu,uk,us",
        the_odds_api_markets="h2h",
        the_odds_api_odds_format="decimal",
        the_odds_api_sport_key="upcoming",
    )
    client = OddsApiClient(settings)
    url = client._url("/sports/upcoming/odds", {
        "apiKey": "test-key",
        "regions": settings.the_odds_api_regions,
        "markets": settings.the_odds_api_markets,
        "oddsFormat": settings.the_odds_api_odds_format,
    })
    assert url.startswith("https://api.the-odds-api.com/v4/sports/upcoming/odds/")
    assert "apiKey=test-key" in url
    assert "markets=h2h" in url
    assert "oddsFormat=decimal" in url
