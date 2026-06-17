from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import demo_fixtures, source_context
from app.schemas import Probabilities
from app.services.model_evaluation_service import actual_outcome, brier_score, log_loss, summarize_predictions
from app.services.prediction_service import PredictionService


def test_actual_outcome_detects_home_draw_away() -> None:
    fixtures = demo_fixtures()
    assert actual_outcome(fixtures[0]) == "home_win"
    assert actual_outcome(fixtures[1]) == "draw"


def test_probability_scores_are_non_negative() -> None:
    probabilities = Probabilities(home_win=0.5, draw=0.25, away_win=0.25)
    assert brier_score(probabilities, "home_win") >= 0
    assert log_loss(probabilities, "home_win") >= 0


def test_summarize_predictions_returns_metrics() -> None:
    service = PredictionService(model_version="test")
    context = source_context()
    fixtures = demo_fixtures()
    summary = summarize_predictions((fixture, service.predict_fixture(fixture, source_context=context)) for fixture in fixtures)
    assert summary["matches_evaluated"] == 2
    assert summary["accuracy"] is not None
    assert summary["brier_score"] is not None
    assert summary["log_loss"] is not None
