from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.fixture_ingestion_service import (
    FixtureIngestionService,
    dedupe_fixtures,
    normalize_api_football_records,
    normalize_espn_scoreboard_records,
    normalize_generic_fixture_records,
    normalize_openfootball_records,
    normalize_thesportsdb_records,
)
from app.services.sources.base import SourceAdapterResult
from scripts.fixture_ingestion_service import (
    PHASE_ONE_FIXTURE_SOURCE_KEYS,
    FixtureIngestionService as ReportFixtureIngestionService,
)
from scripts.source_report_schema import validate_source_report


def test_normalize_openfootball_records_extracts_fixture() -> None:
    payload = {
        "rounds": [
            {
                "name": "Group A",
                "matches": [
                    {
                        "date": "2026-06-11",
                        "team1": {"name": "Mexico"},
                        "team2": {"name": "South Africa"},
                        "venue": "Estadio Azteca",
                    }
                ],
            }
        ]
    }
    records = normalize_openfootball_records(payload, source_key="openfootball_worldcup_json")
    assert len(records) == 1
    assert records[0]["home_team_name"] == "Mexico"
    assert records[0]["away_team_name"] == "South Africa"
    assert records[0]["status"] == "scheduled"


def test_normalize_espn_scoreboard_records_extracts_fixture() -> None:
    payload = {
        "events": [
            {
                "id": "401",
                "date": "2026-06-11T19:00Z",
                "status": {"type": {"state": "pre", "completed": False}},
                "competitions": [
                    {
                        "venue": {"fullName": "Estadio Azteca"},
                        "competitors": [
                            {"homeAway": "home", "team": {"displayName": "Mexico"}, "score": "0"},
                            {"homeAway": "away", "team": {"displayName": "South Africa"}, "score": "0"},
                        ],
                    }
                ],
            }
        ]
    }
    records = normalize_espn_scoreboard_records(payload, source_key="espn_scoreboard")
    assert len(records) == 1
    assert records[0]["source_event_id"] == "401"
    assert records[0]["home_team_name"] == "Mexico"
    assert records[0]["away_team_name"] == "South Africa"


def test_normalize_api_football_records_extracts_fixture() -> None:
    payload = {
        "response": [
            {
                "fixture": {
                    "id": 123,
                    "date": "2026-06-11T19:00:00+00:00",
                    "venue": {"name": "Estadio Azteca"},
                    "status": {"short": "NS", "long": "Not Started", "elapsed": None},
                },
                "league": {"round": "Group Stage - 1"},
                "teams": {"home": {"name": "Mexico"}, "away": {"name": "Canada"}},
                "goals": {"home": None, "away": None},
            }
        ]
    }
    records = normalize_api_football_records(payload, source_key="api_football")
    assert len(records) == 1
    assert records[0]["source_event_id"] == "123"
    assert records[0]["home_team_name"] == "Mexico"
    assert records[0]["away_team_name"] == "Canada"
    assert records[0]["status"] == "scheduled"


def test_normalize_thesportsdb_records_extracts_fixture() -> None:
    payload = {
        "events": [
            {
                "idEvent": "555",
                "strHomeTeam": "USA",
                "strAwayTeam": "Wales",
                "dateEvent": "2026-06-12",
                "strTime": "20:00:00",
                "strVenue": "Example Stadium",
            }
        ]
    }
    records = normalize_thesportsdb_records(payload, source_key="thesportsdb_worldcup")
    assert len(records) == 1
    assert records[0]["kickoff_time"] == "2026-06-12T20:00:00"
    assert records[0]["venue"] == "Example Stadium"


def test_normalize_generic_fixture_records_extracts_fixture() -> None:
    payload = {
        "matches": [
            {
                "match_id": "abc",
                "home_team": {"name": "Argentina"},
                "away_team": {"name": "France"},
                "match_date": "2026-07-19T19:00:00Z",
                "stadium": "MetLife Stadium",
                "round": "Final",
            }
        ]
    }
    records = normalize_generic_fixture_records(payload, source_key="worldcup_2026_api")
    assert len(records) == 1
    assert records[0]["source_event_id"] == "abc"
    assert records[0]["stage"] == "Final"


def test_normalize_generic_fixture_records_supports_sportsdataio_names() -> None:
    payload = {
        "Games": [
            {
                "GameId": 777,
                "HomeTeamName": "Mexico",
                "AwayTeamName": "Canada",
                "DateTime": "2026-06-11T19:00:00Z",
                "Venue": "Estadio Azteca",
                "Round": "Group Stage",
            }
        ]
    }
    records = normalize_generic_fixture_records(payload, source_key="sportsdataio_worldcup")
    assert len(records) == 1
    assert records[0]["source_event_id"] == "777"
    assert records[0]["home_team_name"] == "Mexico"
    assert records[0]["away_team_name"] == "Canada"


def test_sportsdataio_requires_world_cup_ids_when_enabled() -> None:
    settings = SimpleNamespace(
        sportsdataio_enabled=True,
        sportsdataio_api_key="key",
        sportsdataio_base_url="https://api.sportsdata.io/v4/soccer",
        sportsdataio_world_cup_competition_id=None,
        sportsdataio_world_cup_competition_key=None,
        sportsdataio_world_cup_season_id=None,
        sportsdataio_world_cup_season=None,
    )
    result = FixtureIngestionService(settings).sportsdataio_worldcup()
    assert result.status == "missing_world_cup_ids"
    assert result.record_count == 0


def test_feature_sources_report_readiness_not_fixture_records() -> None:
    settings = SimpleNamespace(fifa_ranking_url="https://inside.fifa.com/fifa-world-ranking/men", fifa_ranking_enabled=True)
    result = FixtureIngestionService(settings).fifa_ranking_source()
    assert result.source_key == "fifa_ranking_source"
    assert result.ok is True
    assert result.status == "ranking_snapshot_source_not_fixture_ingestion"
    assert result.records == []


def test_tournamental_bot_arena_missing_credentials_does_not_crash() -> None:
    settings = SimpleNamespace(
        tournamental_enabled=True,
        tournamental_enable_read_only_feeds=True,
        tournamental_api_key=None,
        tournamental_base_url="https://play.tournamental.com",
        tournamental_tournament_id="fifa-wc-2026",
        tournamental_enable_pick_submission=False,
    )
    result = FixtureIngestionService(settings).tournamental_bot_arena()
    assert result.source_key == "tournamental_bot_arena"
    assert result.ok is False
    assert result.status == "missing_credentials"
    assert result.records == []


def test_tournamental_bot_arena_is_read_only_and_not_fixture_ingestion() -> None:
    settings = SimpleNamespace(
        tournamental_enabled=True,
        tournamental_enable_read_only_feeds=True,
        tournamental_api_key="tnm_test",
        tournamental_base_url="https://play.tournamental.com",
        tournamental_tournament_id="fifa-wc-2026",
        tournamental_enable_pick_submission=False,
    )
    result = FixtureIngestionService(settings).tournamental_bot_arena()
    assert result.source_key == "tournamental_bot_arena"
    assert result.ok is True
    assert result.status == "read_only_benchmark_not_fixture_ingestion"
    assert result.record_count == 1
    assert result.records[0]["safety_note"] == "adapter does not submit picks or trigger live betting"


def test_backend_fixture_ingestion_emits_valid_source_reports(monkeypatch) -> None:
    class FakeAdapter:
        produces_fixtures = True
        source_key = "football_data"

        async def fetch(self) -> SourceAdapterResult:
            return SourceAdapterResult(
                source_key="football_data",
                attempted=True,
                configured=True,
                enabled=True,
                ok=False,
                status="parse_error",
                error="json decode failed",
                record_count=0,
                records=[],
                generated_at="2026-06-20T00:00:00+00:00",
            )

    monkeypatch.setattr(
        "app.services.fixture_ingestion_service.build_source_adapters",
        lambda settings, timeout_seconds: [FakeAdapter()],
    )

    report = FixtureIngestionService(SimpleNamespace()).ingest()

    assert report["sources"][0]["status"] == "parse_error"
    assert len(report["source_reports"]) == 1
    assert report["source_reports"][0]["source"]["key"] == "football_data"
    assert report["source_reports"][0]["status"] == "schema_mismatch"
    assert report["source_reports"][0]["success"] is False
    validate_source_report(report["source_reports"][0])


def test_dedupe_prefers_espn_over_openfootball_for_same_fixture() -> None:
    openfootball = normalize_openfootball_records({"matches": [{"date": "2026-06-11", "team1": "Mexico", "team2": "South Africa"}]}, "openfootball_worldcup_json")
    espn = normalize_espn_scoreboard_records({
        "events": [{
            "id": "401",
            "date": "2026-06-11",
            "status": {"type": {"state": "pre", "completed": False}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "Mexico"}},
                {"homeAway": "away", "team": {"displayName": "South Africa"}},
            ]}],
        }]
    }, "espn_scoreboard")
    records = dedupe_fixtures(openfootball + espn)
    assert len(records) == 1
    assert records[0]["source_key"] == "espn_scoreboard"


def test_dedupe_prefers_api_football_over_espn_for_same_fixture() -> None:
    api_football = normalize_api_football_records({
        "response": [{
            "fixture": {"id": 123, "date": "2026-06-11", "status": {"short": "NS"}},
            "league": {"round": "Group A"},
            "teams": {"home": {"name": "Mexico"}, "away": {"name": "South Africa"}},
            "goals": {"home": None, "away": None},
        }]
    }, "api_football")
    espn = normalize_espn_scoreboard_records({
        "events": [{
            "id": "401",
            "date": "2026-06-11",
            "status": {"type": {"state": "pre", "completed": False}},
            "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "Mexico"}},
                {"homeAway": "away", "team": {"displayName": "South Africa"}},
            ]}],
        }]
    }, "espn_scoreboard")
    records = dedupe_fixtures(espn + api_football)
    assert len(records) == 1
    assert records[0]["source_key"] == "api_football"


def test_phase_one_fixture_source_keys_are_limited_to_approved_sources() -> None:
    assert PHASE_ONE_FIXTURE_SOURCE_KEYS == (
        "football_data",
        "api_football",
        "worldcup_2026_api",
        "openfootball_worldcup_json",
        "sportsdataio_worldcup",
        "thestatsapi_worldcup",
    )


def test_report_fixture_ingestion_merges_fixture_provenance() -> None:
    env = {"FOOTBALL_DATA_TOKEN": "fake-football-data", "API_FOOTBALL_KEY": "fake-api-football"}
    adapters = {
        "football_data": lambda: [
            {
                "id": "fd-1",
                "home_team_name": "Argentina",
                "away_team_name": "France",
                "kickoff_time": "2026-07-19T19:00:00Z",
                "venue": "MetLife Stadium",
                "stage": "Final",
            }
        ],
        "api_football": lambda: [
            {
                "id": "api-1",
                "home_team": {"name": "Argentina"},
                "away_team": {"name": "France"},
                "date": "2026-07-19T19:00:00Z",
                "round": "Final",
            }
        ],
    }

    report = ReportFixtureIngestionService(adapters, env, fixture_source_keys=("football_data", "api_football")).run()

    assert report["fixture_count"] == 1
    assert report["merged_fixture_count"] == 1
    assert report["teams_count"] == 2
    assert report["groups_count"] == 1
    fixture = report["fixtures"][0]
    assert fixture["source_keys"] == ["football_data", "api_football"]
    assert [item["source_key"] for item in fixture["source_provenance"]] == ["football_data", "api_football"]
    assert {source["status"] for source in report["source_reports"]} == {"ok"}
    serialized = json.dumps(report)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


def test_report_fixture_ingestion_missing_env_and_missing_adapter_do_not_crash() -> None:
    report = ReportFixtureIngestionService(adapters={}, environ={}).run()
    statuses = {item["source"]["key"]: item["status"] for item in report["source_reports"]}

    assert report["fixture_count"] == 0
    assert statuses["football_data"] == "missing_credentials"
    assert statuses["api_football"] == "missing_credentials"
    assert statuses["worldcup_2026_api"] == "disabled"
    assert statuses["openfootball_worldcup_json"] == "disabled"
    assert statuses["sportsdataio_worldcup"] == "disabled"
    assert statuses["thestatsapi_worldcup"] == "disabled"
    assert "openfootball_worldcup_json: adapter_not_configured" in report["warnings"]
    assert report["safety"] == {
        "live_betting_allowed": False,
        "automated_wagering_allowed": False,
        "real_money_betting_allowed": False,
        "pick_submission_allowed": False,
    }


def test_report_fixture_ingestion_records_timeout_empty_and_schema_mismatch() -> None:
    env = {
        "FOOTBALL_DATA_TOKEN": "fake-football-data",
        "API_FOOTBALL_KEY": "fake-api-football",
        "WORLD_CUP_2026_API_BASE_URL": "https://example.test/worldcup",
        "WORLD_CUP_2026_API_ENABLED": "true",
    }

    def timeout_adapter() -> list[dict]:
        raise TimeoutError("provider timed out")

    adapters = {
        "football_data": lambda: [{"id": "bad-record-without-teams"}],
        "api_football": timeout_adapter,
        "worldcup_2026_api": lambda: [],
    }

    report = ReportFixtureIngestionService(
        adapters,
        env,
        fixture_source_keys=("football_data", "api_football", "worldcup_2026_api"),
    ).run()
    statuses = {item["source"]["key"]: item["status"] for item in report["source_reports"]}

    assert report["fixture_count"] == 0
    assert statuses["football_data"] == "schema_mismatch"
    assert statuses["api_football"] == "timeout"
    assert statuses["worldcup_2026_api"] == "empty_response"
    assert any("schema_mismatch" in error for error in report["errors"])
    assert any("timeout" in error for error in report["errors"])


def test_report_fixture_ingestion_writes_json_report(tmp_path: Path) -> None:
    env = {"FOOTBALL_DATA_TOKEN": "fake-football-data"}
    adapters = {
        "football_data": lambda: [
            {
                "id": "fd-1",
                "home_team_name": "Mexico",
                "away_team_name": "Canada",
                "kickoff_time": "2026-06-11T19:00:00Z",
                "stage": "Group A",
            }
        ],
    }
    report_path = tmp_path / "fixture_ingestion_report.json"

    report = ReportFixtureIngestionService(adapters, env, fixture_source_keys=("football_data",)).write_report(report_path)
    saved = json.loads(report_path.read_text(encoding="utf-8"))

    assert saved["run_id"] == report["run_id"]
    assert saved["fixture_count"] == 1
    assert saved["source_reports"][0]["status"] == "ok"
    assert saved["fixtures"][0]["source_provenance"][0]["source_key"] == "football_data"
