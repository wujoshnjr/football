from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.football_data_client import FootballDataClient, normalize_football_data_matches


def test_football_data_client_reports_missing_token() -> None:
    settings = SimpleNamespace(
        football_data_base_url="https://api.football-data.org/v4",
        football_data_token=None,
        football_data_worldcup_competition_code="WC",
    )
    client = FootballDataClient(settings)
    result = client.worldcup_matches()
    assert result.configured is False
    assert result.ok is False
    assert result.error == "missing_token"


def test_normalize_football_data_matches() -> None:
    payload = {
        "matches": [
            {
                "id": 1,
                "utcDate": "2026-06-11T20:00:00Z",
                "status": "SCHEDULED",
                "stage": "GROUP_STAGE",
                "group": "GROUP_A",
                "matchday": 1,
                "homeTeam": {"name": "Mexico"},
                "awayTeam": {"name": "South Africa"},
                "score": {"fullTime": {"home": None, "away": None}},
            },
            {
                "id": 2,
                "utcDate": "2026-06-12T00:00:00Z",
                "status": "FINISHED",
                "stage": "GROUP_STAGE",
                "homeTeam": {"name": "Canada"},
                "awayTeam": {"name": "Qatar"},
                "score": {"fullTime": {"home": 2, "away": 1}},
            },
        ]
    }
    rows = normalize_football_data_matches(payload)
    assert len(rows) == 2
    assert rows[0]["source_key"] == "football_data"
    assert rows[0]["home_team_name"] == "Mexico"
    assert rows[0]["away_team_name"] == "South Africa"
    assert rows[0]["status"] == "scheduled"
    assert rows[1]["status"] == "finished"
    assert rows[1]["home_score"] == 2
    assert rows[1]["away_score"] == 1
