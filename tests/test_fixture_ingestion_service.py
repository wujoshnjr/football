from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
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
