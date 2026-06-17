from __future__ import annotations

from math import log
from typing import Iterable

from app.schemas import Fixture, PredictionResponse, Probabilities

OUTCOMES = ("home_win", "draw", "away_win")


def actual_outcome(fixture: Fixture) -> str | None:
    if fixture.home_score is None or fixture.away_score is None:
        return None
    if fixture.home_score > fixture.away_score:
        return "home_win"
    if fixture.home_score == fixture.away_score:
        return "draw"
    return "away_win"


def predicted_outcome(probabilities: Probabilities) -> str:
    values = probabilities.model_dump()
    return max(values.items(), key=lambda item: item[1])[0]


def brier_score(probabilities: Probabilities, outcome: str) -> float:
    values = probabilities.model_dump()
    return round(sum((values[key] - (1.0 if key == outcome else 0.0)) ** 2 for key in OUTCOMES), 6)


def log_loss(probabilities: Probabilities, outcome: str) -> float:
    values = probabilities.model_dump()
    probability = max(min(values[outcome], 0.999999), 0.000001)
    return round(-log(probability), 6)


def summarize_predictions(rows: Iterable[tuple[Fixture, PredictionResponse]]) -> dict:
    evaluated = []
    for fixture, prediction in rows:
        outcome = actual_outcome(fixture)
        if outcome is None:
            continue
        predicted = predicted_outcome(prediction.probabilities)
        evaluated.append({
            "fixture_id": fixture.id,
            "match": prediction.match,
            "actual_outcome": outcome,
            "predicted_outcome": predicted,
            "correct": predicted == outcome,
            "brier_score": brier_score(prediction.probabilities, outcome),
            "log_loss": log_loss(prediction.probabilities, outcome),
            "probabilities": prediction.probabilities.model_dump(),
            "confidence": prediction.confidence,
            "reason_codes": prediction.diagnostics.reason_codes if prediction.diagnostics else [],
            "risk_flags": prediction.diagnostics.risk_flags if prediction.diagnostics else [],
        })

    if not evaluated:
        return {
            "matches_evaluated": 0,
            "accuracy": None,
            "brier_score": None,
            "log_loss": None,
            "rows": [],
            "evaluation_note": "No finished fixtures with scores were available for evaluation.",
        }

    return {
        "matches_evaluated": len(evaluated),
        "accuracy": round(sum(row["correct"] for row in evaluated) / len(evaluated), 6),
        "brier_score": round(sum(row["brier_score"] for row in evaluated) / len(evaluated), 6),
        "log_loss": round(sum(row["log_loss"] for row in evaluated) / len(evaluated), 6),
        "rows": evaluated,
        "evaluation_note": "MVP evaluation over finished fixtures only. Larger backtests are required before making model-quality claims.",
    }
