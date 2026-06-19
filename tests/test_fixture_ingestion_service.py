from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.fixture_ingestion_service import (
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
