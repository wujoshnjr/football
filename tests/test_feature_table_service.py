from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import demo_fixtures, match_feature_rows


def test_feature_table_has_one_row_per_fixture() -> None:
    fixtures = demo_fixtures()
    rows = match_feature_rows()
    assert len(rows) == len(fixtures)


def test_feature_table_contains_core_model_features() -> None:
    row = match_feature_rows()[0]
    required_columns = {
        "fixture_id",
        "prediction_cutoff",
        "status",
        "is_final",
        "home_elo",
        "away_elo",
        "elo_diff",
        "recent_points_diff",
        "attack_defense_signal",
        "source_reliability_score",
        "fixture_consensus_score",
        "leakage_policy",
    }
    assert required_columns.issubset(row.keys())


def test_feature_table_does_not_expose_score_inputs_for_model_features() -> None:
    rows = match_feature_rows()
    for row in rows:
        assert "home_score" not in row
        assert "away_score" not in row
        assert "score" not in row["leakage_policy"].lower() or "no finished-match score" in row["leakage_policy"].lower()
