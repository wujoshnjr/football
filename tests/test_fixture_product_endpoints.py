from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import main

client = TestClient(main.app)


def assert_no_forbidden_betting_keys(payload: Any) -> None:
    serialized = json.dumps(payload)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


FAKE_FIXTURE_RECORDS = [
    {
        "id": "match-completed-1",
        "home_team_name": "Argentina",
        "away_team_name": "Algeria",
        "kickoff_time": "2026-06-18T12:00:00Z",
        "venue": "Kansas City Stadium",
        "stage": "Group J",
        "status": "finished",
        "home_score": 2,
        "away_score": 1,
        "source_provenance": [{"source_key": "football_data", "source_event_id": "fd-1", "role": "fixture_source"}],
        "last_updated_at": "2026-06-18T14:05:00Z",
    },
    {
        "id": "match-tomorrow-1",
        "home_team_name": "Japan",
        "away_team_name": "Tunisia",
        "kickoff_time": "2026-06-20T16:30:00Z",
        "venue": "Estadio Monterrey",
        "stage": "Group F",
        "status": "scheduled",
        "source_key": "openfootball_worldcup_json",
        "last_updated_at": "2026-06-20T00:00:00Z",
    },
    {
        "id": "match-tomorrow-2",
        "home_team_name": "Netherlands",
        "away_team_name": "Sweden",
        "kickoff_time": "2026-06-21T12:00:00Z",
        "venue": "Houston Stadium",
        "stage": "Group F",
        "status": "scheduled",
        "source_key": "api_football",
        "last_updated_at": "2026-06-20T00:00:00Z",
    },
    {
        "id": "match-date-2026-06-22",
        "home_team_name": "Jordan",
        "away_team_name": "Austria",
        "kickoff_time": "2026-06-22T12:00:00Z",
        "venue": "Dallas Stadium",
        "stage": "Group J",
        "status": "scheduled",
        "source_key": "sportsdataio_worldcup",
        "last_updated_at": "2026-06-20T00:00:00Z",
    },
]


def install_fake_fixture_cache(monkeypatch) -> None:
    monkeypatch.setattr(main, "current_date_for_timezone", lambda tz: date(2026, 6, 20))

    def fake_product_records(source: str = "auto"):
        return FAKE_FIXTURE_RECORDS, {
            "source_used": "cache",
            "generated_at": "2026-06-20T00:00:00+00:00",
            "cache_path": "data/cache/fixtures_latest.json",
            "cache_exists": True,
            "warnings": [],
        }

    monkeypatch.setattr(main, "fixture_product_records", fake_product_records)


def test_fixtures_completed_returns_completed_matches_with_scores(monkeypatch) -> None:
    install_fake_fixture_cache(monkeypatch)

    response = client.get("/fixtures/completed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture_count"] == 1
    fixture = payload["fixtures"][0]
    assert fixture["fixture_id"] == "match-completed-1"
    assert fixture["home_team"] == "Argentina"
    assert fixture["away_team"] == "Algeria"
    assert fixture["status"] == "completed"
    assert fixture["home_score"] == 2
    assert fixture["away_score"] == 1
    assert fixture["winner"] == "Argentina"
    assert fixture["result"] == "Argentina win"
    assert fixture["finalized_at"] == "2026-06-18T14:05:00Z"
    assert fixture["source_provenance"][0]["source_key"] == "football_data"
    assert_no_forbidden_betting_keys(payload)


def test_fixtures_tomorrow_returns_all_tomorrow_matches(monkeypatch) -> None:
    install_fake_fixture_cache(monkeypatch)

    response = client.get("/fixtures/tomorrow")

    assert response.status_code == 200
    payload = response.json()
    assert payload["timezone"] == "Asia/Taipei"
    assert payload["fixture_count"] == 2
    assert [fixture["fixture_id"] for fixture in payload["fixtures"]] == ["match-tomorrow-1", "match-tomorrow-2"]
    assert payload["data_completeness"]["tomorrow_count"] == 2
    assert payload["data_completeness"]["cache_exists"] is True
    assert_no_forbidden_betting_keys(payload)


def test_fixtures_date_filters_by_local_date(monkeypatch) -> None:
    install_fake_fixture_cache(monkeypatch)

    response = client.get("/fixtures/date/2026-06-22")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture_count"] == 1
    assert payload["fixtures"][0]["fixture_id"] == "match-date-2026-06-22"
    assert payload["fixtures"][0]["stage"] == "Group J"
    assert_no_forbidden_betting_keys(payload)


def test_fixtures_status_query_filters_completed(monkeypatch) -> None:
    install_fake_fixture_cache(monkeypatch)

    response = client.get("/fixtures", params={"status": "completed"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture_count"] == 1
    assert payload["data_completeness"]["cache_exists"] is True
    assert payload["fixtures"][0]["home_score"] == 2
    assert payload["fixtures"][0]["away_score"] == 1
    assert_no_forbidden_betting_keys(payload)


def test_demo_fallback_is_not_marked_complete_schedule() -> None:
    response = client.get("/fixtures", params={"source": "demo"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_used"] == "demo_fallback"
    assert payload["data_completeness"]["cache_exists"] is False
    assert payload["data_completeness"]["is_complete_worldcup_schedule"] is False
    assert payload["data_completeness"]["missing_reason"] == "demo_fallback_in_use"
    assert payload["data_completeness"]["fixture_count"] == 6
    assert any("Demo fallback" in warning for warning in payload["warnings"])
    assert_no_forbidden_betting_keys(payload)


def test_fixture_cache_status_missing_cache_does_not_crash(monkeypatch, tmp_path) -> None:
    missing_cache = tmp_path / "missing" / "fixtures_latest.json"
    missing_report = tmp_path / "missing" / "worldcup_fixture_cache_report.json"
    monkeypatch.setattr(main, "FIXTURE_CACHE_PATHS", [missing_cache])
    monkeypatch.setattr(main, "WORLD_CUP_FIXTURE_CACHE_REPORT_PATH", missing_report)
    monkeypatch.setattr(main, "current_date_for_timezone", lambda tz: date(2026, 6, 20))

    response = client.get("/fixtures/cache/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["cache_exists"] is False
    assert payload["fixture_count"] == 0
    assert payload["completed_count"] == 0
    assert payload["tomorrow_count"] == 0
    assert payload["scheduled_count"] == 0
    assert payload["is_complete_worldcup_schedule"] is False
    assert payload["missing_reason"] == "fixture_cache_missing_or_empty"
    assert payload["cache_path"] is None
    assert payload["source_used"] == "cache_missing"
    assert_no_forbidden_betting_keys(payload)
