from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from app.schemas import Fixture, SourceFeatureBundle


@dataclass(frozen=True)
class MatchFeatureRow:
    fixture_id: str
    generated_at: str
    prediction_cutoff: str
    status: str
    is_final: bool
    home_team_id: str
    away_team_id: str
    home_team_name: str
    away_team_name: str
    home_elo: float
    away_elo: float
    elo_diff: float
    home_recent_points_per_match: float
    away_recent_points_per_match: float
    recent_points_diff: float
    home_goals_for_per_match: float
    away_goals_for_per_match: float
    home_goals_against_per_match: float
    away_goals_against_per_match: float
    attack_defense_signal: float
    source_reliability_score: float
    fixture_consensus_score: float
    source_count: int
    configured_source_count: int
    missing_source_count: int
    leakage_policy: str


def build_match_feature_table(fixtures: Iterable[Fixture], source_context: SourceFeatureBundle) -> list[dict]:
    generated_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []

    for fixture in fixtures:
        is_final = fixture.status.lower() in {"finished", "final", "full_time"}
        home = fixture.home_team
        away = fixture.away_team
        row = MatchFeatureRow(
            fixture_id=fixture.id,
            generated_at=generated_at,
            prediction_cutoff=fixture.kickoff_time,
            status=fixture.status,
            is_final=is_final,
            home_team_id=home.id,
            away_team_id=away.id,
            home_team_name=home.name,
            away_team_name=away.name,
            home_elo=home.elo_rating,
            away_elo=away.elo_rating,
            elo_diff=round(home.elo_rating - away.elo_rating, 3),
            home_recent_points_per_match=home.recent_points_per_match,
            away_recent_points_per_match=away.recent_points_per_match,
            recent_points_diff=round(home.recent_points_per_match - away.recent_points_per_match, 3),
            home_goals_for_per_match=home.goals_for_per_match,
            away_goals_for_per_match=away.goals_for_per_match,
            home_goals_against_per_match=home.goals_against_per_match,
            away_goals_against_per_match=away.goals_against_per_match,
            attack_defense_signal=round((home.goals_for_per_match - away.goals_against_per_match) - (away.goals_for_per_match - home.goals_against_per_match), 3),
            source_reliability_score=source_context.reliability_score,
            fixture_consensus_score=source_context.fixture_consensus_score,
            source_count=len(source_context.sources_used),
            configured_source_count=len(source_context.sources_configured),
            missing_source_count=len(source_context.sources_missing),
            leakage_policy="pre_match_only_features; no finished-match score fields are used as model inputs",
        )
        rows.append(asdict(row))

    return rows
