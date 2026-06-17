from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.fixture_ingestion_service import (
    dedupe_fixtures,
    normalize_espn_scoreboard_records,
    normalize_openfootball_records,
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
