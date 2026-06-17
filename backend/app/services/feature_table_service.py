from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

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
    market_signal_available: bool
    market_source_event_id: str | None
    market_source_sport_key: str | None
    market_home_implied_probability: float | None
    market_draw_implied_probability: float | None
    market_away_implied_probability: float | None
    market_bookmaker_count: int
    market_signal_note: str
    leakage_policy: str


def build_match_feature_table(
    fixtures: Iterable[Fixture],
    source_context: SourceFeatureBundle,
    market_consensus: dict[str, Any] | None = None,
) -> list[dict]:
    generated_at = datetime.now(timezone.utc).isoformat()
    market_index = build_market_consensus_index(market_consensus)
    rows: list[dict] = []

    for fixture in fixtures:
        is_final = fixture.status.lower() in {"finished", "final", "full_time"}
        home = fixture.home_team
        away = fixture.away_team
        market = market_index.get(match_key(home.name, away.name))
        market_signal = extract_fixture_market_signal(fixture, market)
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
            market_signal_available=market_signal["available"],
            market_source_event_id=market_signal["event_id"],
            market_source_sport_key=market_signal["sport_key"],
            market_home_implied_probability=market_signal["home_implied_probability"],
            market_draw_implied_probability=market_signal["draw_implied_probability"],
            market_away_implied_probability=market_signal["away_implied_probability"],
            market_bookmaker_count=market_signal["bookmaker_count"],
            market_signal_note=market_signal["note"],
            leakage_policy="pre_match_only_features; no finished-match score fields are used as model inputs; market odds must be timestamped before prediction cutoff",
        )
        rows.append(asdict(row))

    return rows


def build_market_consensus_index(market_consensus: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    if not market_consensus:
        return {}

    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for item in market_consensus.get("market_consensus", []):
        home = item.get("home_team")
        away = item.get("away_team")
        if not home or not away:
            continue
        indexed[match_key(home, away)] = item
    return indexed


def extract_fixture_market_signal(fixture: Fixture, market: dict[str, Any] | None) -> dict[str, Any]:
    if not market:
        return {
            "available": False,
            "event_id": None,
            "sport_key": None,
            "home_implied_probability": None,
            "draw_implied_probability": None,
            "away_implied_probability": None,
            "bookmaker_count": 0,
            "note": "No matching market-consensus event was found for this fixture.",
        }

    consensus = market.get("consensus", {})
    home_signal = find_outcome_signal(consensus, fixture.home_team.name)
    away_signal = find_outcome_signal(consensus, fixture.away_team.name)
    draw_signal = find_draw_signal(consensus)

    bookmaker_count = max(
        int(home_signal.get("bookmaker_count", 0)) if home_signal else 0,
        int(draw_signal.get("bookmaker_count", 0)) if draw_signal else 0,
        int(away_signal.get("bookmaker_count", 0)) if away_signal else 0,
    )
    return {
        "available": bool(home_signal or draw_signal or away_signal),
        "event_id": market.get("event_id"),
        "sport_key": market.get("sport_key"),
        "home_implied_probability": implied_probability(home_signal),
        "draw_implied_probability": implied_probability(draw_signal),
        "away_implied_probability": implied_probability(away_signal),
        "bookmaker_count": bookmaker_count,
        "note": "Matched by normalized home/away team names from The Odds API h2h consensus.",
    }


def find_outcome_signal(consensus: dict[str, Any], team_name: str) -> dict[str, Any] | None:
    target = normalize_name(team_name)
    for outcome_name, signal in consensus.items():
        if normalize_name(outcome_name) == target:
            return signal
    return None


def find_draw_signal(consensus: dict[str, Any]) -> dict[str, Any] | None:
    draw_aliases = {"draw", "tie", "x"}
    for outcome_name, signal in consensus.items():
        if normalize_name(outcome_name) in draw_aliases:
            return signal
    return None


def implied_probability(signal: dict[str, Any] | None) -> float | None:
    if not signal:
        return None
    value = signal.get("implied_probability")
    return float(value) if isinstance(value, (int, float)) else None


def match_key(home_name: str, away_name: str) -> tuple[str, str]:
    return normalize_name(home_name), normalize_name(away_name)


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())
