from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adapters.tournamental_bot_arena_adapter import AdapterHTTPError, TournamentalBotArenaAdapter


def configured_env(**overrides: str) -> dict[str, str]:
    env = {
        "TOURNAMENTAL_ENABLED": "true",
        "TOURNAMENTAL_BASE_URL": "https://arena.example.test",
        "TOURNAMENTAL_API_KEY": "fake-key-for-tests",
        "TOURNAMENTAL_TOURNAMENT_ID": "fifa-wc-2026",
        "TOURNAMENTAL_ENABLE_READ_ONLY_FEEDS": "true",
        "TOURNAMENTAL_ENABLE_PICK_SUBMISSION": "false",
    }
    env.update(overrides)
    return env


def test_missing_key_does_not_crash_and_returns_json_report() -> None:
    adapter = TournamentalBotArenaAdapter(environ={"TOURNAMENTAL_ENABLED": "true"})

    report = adapter.get_match_catalogue()

    assert report["source"] == "tournamental_bot_arena"
    assert report["records"] == []
    assert report["record_count"] == 0
    assert report["source_report"]["success"] is False
    assert report["source_report"]["status"] == "missing_credentials"
    assert report["safety"]["pick_submission_allowed"] is False
    assert report["safety"]["live_betting_allowed"] is False


def test_pick_submission_is_locked_false_even_when_requested() -> None:
    adapter = TournamentalBotArenaAdapter(
        environ=configured_env(TOURNAMENTAL_ENABLE_PICK_SUBMISSION="true"),
        http_get=lambda url, headers, params, timeout: {"matches": []},
    )

    report = adapter.health_check()

    assert report["safety"]["pick_submission_requested"] is True
    assert report["safety"]["pick_submission_allowed"] is False
    assert report["safety"]["pick_submission_locked"] is True
    assert report["warnings"]
    assert not hasattr(adapter, "submit_pick")
    assert not hasattr(adapter, "submit_bulk_picks")
    assert not hasattr(adapter, "run_bot_swarm")


def test_match_catalogue_uses_fake_client_and_preserves_source_provenance() -> None:
    def fake_get(url: str, headers: Mapping[str, str], params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        assert url.endswith("/tournaments/fifa-wc-2026/matches")
        assert headers["Authorization"] == "Bearer fake-key-for-tests"
        return {
            "matches": [
                {
                    "fixture_id": "wc-001",
                    "home_team": "Canada",
                    "away_team": "Mexico",
                    "recommended_bet": "forbidden upstream field",
                    "stake_size": 10,
                }
            ]
        }

    adapter = TournamentalBotArenaAdapter(environ=configured_env(), http_get=fake_get)
    report = adapter.get_match_catalogue()

    assert report["source_report"]["status"] == "ok"
    assert report["record_count"] == 1
    record = report["records"][0]
    assert record["fixture_id"] == "wc-001"
    assert record["source_provenance"][0]["source"] == "tournamental_bot_arena"
    serialized = json.dumps(report, sort_keys=True)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


def test_odds_are_labeled_as_market_consensus_external_signal_or_paper_tracking() -> None:
    def fake_get(url: str, headers: Mapping[str, str], params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        return {"odds": [{"fixture_id": "wc-001", "home_odds": 2.1, "draw_odds": 3.2, "away_odds": 3.7}]}

    adapter = TournamentalBotArenaAdapter(environ=configured_env(), http_get=fake_get)
    report = adapter.get_odds(match_id="wc-001")

    assert report["source_report"]["status"] == "ok"
    assert report["signal_roles"] == ["market_consensus", "external_signal", "paper_tracking"]
    assert report["records"][0]["signal_role"] == "market_consensus"
    assert report["records"][0]["allowed_signal_roles"] == ["market_consensus", "external_signal", "paper_tracking"]


def test_rate_limit_is_reported_without_crashing() -> None:
    def fake_get(url: str, headers: Mapping[str, str], params: Mapping[str, Any], timeout: float) -> dict[str, Any]:
        raise AdapterHTTPError(429, "too many requests")

    adapter = TournamentalBotArenaAdapter(environ=configured_env(), http_get=fake_get)
    report = adapter.get_weather(match_id="wc-001")

    assert report["records"] == []
    assert report["source_report"]["status"] == "rate_limited"
    assert report["source_report"]["error"] == "too many requests"
    assert report["safety"]["automated_wagering_allowed"] is False


def test_schema_mismatch_is_reported_without_crashing() -> None:
    adapter = TournamentalBotArenaAdapter(environ=configured_env(), http_get=lambda url, headers, params, timeout: {"unexpected": {}})

    report = adapter.get_injuries(match_id="wc-001")

    assert report["records"] == []
    assert report["source_report"]["status"] == "schema_mismatch"
