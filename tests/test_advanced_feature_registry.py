from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.advanced_feature_registry import advanced_feature_registry


REQUIRED_KEYS = {
    "team_elo_strength",
    "attack_defense_split",
    "xg_xt_profile",
    "player_availability_load",
    "referee_card_profile",
    "environment_context",
    "market_consensus_signal",
    "spatial_unpredictability_index",
    "video_micro_features",
    "bayesian_uncertainty_update",
    "ensemble_model_stack",
    "incremental_learning_guardrails",
    "draw_probability_specialist",
}


def test_advanced_feature_registry_contains_required_features() -> None:
    features = advanced_feature_registry()
    keys = {item["key"] for item in features}
    assert REQUIRED_KEYS.issubset(keys)


def test_advanced_feature_registry_is_english_and_has_risk_labels() -> None:
    features = advanced_feature_registry()
    for item in features:
        assert item["description"]
        assert item["model_use"]
        assert item["leakage_risk"]
        assert "資料" not in item["description"]
        assert "賽程" not in item["description"]
