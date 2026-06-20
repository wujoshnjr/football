from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_calibration_report import (
    OUTCOMES,
    build_calibration_report,
    multiclass_brier_score,
    multiclass_log_loss,
)
from scripts.football_model_vs_market_report import (
    build_model_vs_market_report,
    no_vig_1x2_from_decimal_odds,
)


def sample_rows() -> list[dict[str, object]]:
    return [
        {
            "fixture_id": "wc-001",
            "stage": "Group A",
            "model_home_prob": 0.70,
            "model_draw_prob": 0.20,
            "model_away_prob": 0.10,
            "actual_result": "home_win",
            "market_home_prob": 0.60,
            "market_draw_prob": 0.25,
            "market_away_prob": 0.15,
            "opening_home_odds": 2.10,
            "opening_draw_odds": 3.40,
            "opening_away_odds": 4.20,
            "closing_home_odds": 1.90,
            "closing_draw_odds": 3.50,
            "closing_away_odds": 4.80,
            "source_provenance": [{"source": "football_data"}],
        },
        {
            "fixture_id": "wc-002",
            "stage": "Group B",
            "model_home_prob": 0.30,
            "model_draw_prob": 0.40,
            "model_away_prob": 0.30,
            "actual_result": "draw",
            "market_home_prob": 0.35,
            "market_draw_prob": 0.30,
            "market_away_prob": 0.35,
            "opening_market_home_prob": 0.36,
            "opening_market_draw_prob": 0.29,
            "opening_market_away_prob": 0.35,
            "closing_market_home_prob": 0.34,
            "closing_market_draw_prob": 0.31,
            "closing_market_away_prob": 0.35,
            "source_provenance": [{"source": "api_football"}],
        },
        {
            "fixture_id": "wc-003",
            "stage": "Quarterfinal",
            "model_home_prob": 0.20,
            "model_draw_prob": 0.25,
            "model_away_prob": 0.55,
            "actual_result": "away_win",
            "market_home_prob": 0.22,
            "market_draw_prob": 0.28,
            "market_away_prob": 0.50,
            "source_provenance": [{"source": "thestatsapi_worldcup"}],
        },
        {
            "fixture_id": "wc-004",
            "stage": "Final",
            "model_home_prob": 0.45,
            "model_draw_prob": 0.30,
            "model_away_prob": 0.25,
            "final_home_score": 2,
            "final_away_score": 1,
            "home_odds": 2.50,
            "draw_odds": 3.20,
            "away_odds": 3.10,
            "source_provenance": [{"source": "sportsdataio_worldcup"}],
        },
    ]


def test_multiclass_brier_and_logloss_known_single_sample() -> None:
    rows = [
        {
            "model_home_prob": 0.70,
            "model_draw_prob": 0.20,
            "model_away_prob": 0.10,
            "actual_result": "home_win",
        }
    ]

    assert multiclass_brier_score(rows) == pytest.approx(0.14)
    assert multiclass_log_loss(rows) == pytest.approx(-math.log(0.70))


def test_calibration_report_has_outcomes_slices_and_source_provenance() -> None:
    report = build_calibration_report(sample_rows(), min_samples=2, bin_count=3)

    assert report["status"] == "ok"
    assert report["sample_count"] == 4
    assert set(report["calibration"]) == set(OUTCOMES)
    assert "group_stage" in report["slices"]["stage"]
    assert "knockout" in report["slices"]["stage"]
    assert "favorite_result" in report["slices"]["favorite_vs_underdog"]
    assert report["source_provenance"]["source_counts"]["football_data"] == 1
    assert report["safety"]["live_betting_allowed"] is False


def test_low_sample_calibration_reports_insufficient_sample() -> None:
    report = build_calibration_report(sample_rows()[:1], min_samples=10)

    assert report["status"] == "insufficient_sample"
    assert report["sample_count"] == 1
    assert report["minimum_sample_count"] == 10


def test_no_vig_1x2_from_decimal_odds_sums_to_one() -> None:
    probabilities = no_vig_1x2_from_decimal_odds(2.0, 4.0, 4.0)

    assert probabilities is not None
    assert sum(probabilities.values()) == pytest.approx(1.0)
    assert probabilities["home_win"] == pytest.approx(0.50)
    assert probabilities["draw"] == pytest.approx(0.25)
    assert probabilities["away_win"] == pytest.approx(0.25)


def test_model_vs_market_report_is_market_consensus_and_paper_tracking_only() -> None:
    report = build_model_vs_market_report(sample_rows(), min_samples=2, include_rows=True)

    assert report["status"] == "ok"
    assert report["sample_count"] == 4
    assert report["signal_roles"] == ["market_consensus", "external_signal", "paper_tracking"]
    assert report["gap_metrics"]["mean_absolute_gap_all_outcomes"] is not None
    assert report["slices"]["stage"]["group_stage"]["sample_count"] == 2
    assert report["slices"]["stage"]["knockout"]["sample_count"] == 2
    assert report["slices"]["favorite_vs_underdog"]["market_favorite"]["sample_count"] == 4
    assert report["market_movement_evidence"]["role"] == "paper_tracking"
    assert report["market_movement_evidence"]["sample_count"] == 2

    serialized = json.dumps(report, sort_keys=True)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


def test_model_vs_market_low_sample_and_missing_market_are_non_crashing() -> None:
    rows = [
        {
            "fixture_id": "wc-missing-market",
            "stage": "Group C",
            "model_home_prob": 0.50,
            "model_draw_prob": 0.25,
            "model_away_prob": 0.25,
            "actual_result": "home_win",
        }
    ]

    report = build_model_vs_market_report(rows, min_samples=2)

    assert report["status"] == "insufficient_sample"
    assert report["sample_count"] == 0
    assert report["skipped_reasons"] == {"missing_or_invalid_market_consensus": 1}
    assert report["gap_metrics"] is None
