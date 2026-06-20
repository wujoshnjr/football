from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_feature_schema import (
    AVAILABILITY_FLAG_FEATURES,
    CORE_MODEL_FEATURES,
    SHADOW_CANDIDATE_FEATURES,
    TRACKING_ONLY_FEATURES,
    FeatureSchemaError,
    all_feature_specs,
    assert_core_model_features,
    build_feature_schema_report,
    feature_bucket,
    request_feature_promotion,
)


def test_core_model_features_match_conservative_current_table_inputs() -> None:
    expected = {
        "home_elo",
        "away_elo",
        "elo_diff",
        "home_recent_points_per_match",
        "away_recent_points_per_match",
        "recent_points_diff",
        "home_goals_for_per_match",
        "away_goals_for_per_match",
        "home_goals_against_per_match",
        "away_goals_against_per_match",
        "attack_defense_signal",
        "source_reliability_score",
        "fixture_consensus_score",
        "source_count",
    }

    assert set(CORE_MODEL_FEATURES) == expected
    assert_core_model_features(set(CORE_MODEL_FEATURES))


def test_tracking_only_features_include_required_advanced_inputs() -> None:
    required = {
        "lineup_confirmed",
        "home_injury_count",
        "away_injury_count",
        "home_suspension_count",
        "away_suspension_count",
        "home_xg_for",
        "away_xg_for",
        "market_no_vig_home_win",
        "market_no_vig_draw",
        "market_no_vig_away_win",
        "weather_temperature_c",
        "home_news_alert_count",
        "away_news_alert_count",
        "tournamental_market_gap_home",
        "tournamental_market_gap_draw",
        "tournamental_market_gap_away",
    }

    assert required.issubset(TRACKING_ONLY_FEATURES)
    assert TRACKING_ONLY_FEATURES["market_no_vig_home_win"].allowed_use == "market_consensus_tracking_only"
    assert TRACKING_ONLY_FEATURES["tournamental_market_gap_home"].allowed_use == "external_signal_tracking_only"


def test_availability_flags_cover_required_source_types() -> None:
    assert set(AVAILABILITY_FLAG_FEATURES) == {
        "fixture_available",
        "odds_available",
        "lineup_available",
        "injury_available",
        "suspension_available",
        "weather_available",
        "fifa_ranking_available",
        "xg_available",
        "news_available",
    }


def test_shadow_candidate_features_are_defined() -> None:
    assert {
        "draw_probability_specialist_signal",
        "bayesian_team_strength_delta",
        "spatial_unpredictability_index",
        "tournamental_bot_consensus_gap",
    }.issubset(SHADOW_CANDIDATE_FEATURES)


def test_feature_keys_are_unique_across_buckets() -> None:
    all_features = all_feature_specs()
    total_bucket_count = (
        len(CORE_MODEL_FEATURES)
        + len(TRACKING_ONLY_FEATURES)
        + len(AVAILABILITY_FLAG_FEATURES)
        + len(SHADOW_CANDIDATE_FEATURES)
    )

    assert len(all_features) == total_bucket_count


def test_non_core_features_cannot_enter_core_model_silently() -> None:
    with pytest.raises(FeatureSchemaError, match="non-core features"):
        assert_core_model_features(["home_elo", "market_no_vig_home_win"])

    with pytest.raises(FeatureSchemaError, match="unknown features"):
        assert_core_model_features(["home_elo", "mystery_feature"])


def test_feature_bucket_reports_expected_bucket() -> None:
    assert feature_bucket("home_elo") == "core_model"
    assert feature_bucket("weather_temperature_c") == "tracking_only"
    assert feature_bucket("weather_available") == "availability_flag"
    assert feature_bucket("draw_probability_specialist_signal") == "shadow_candidate"


def test_promotion_requires_schema_approval_and_does_not_mutate_buckets() -> None:
    with pytest.raises(FeatureSchemaError, match="approved_by and rationale"):
        request_feature_promotion("market_no_vig_home_win", "core_model")

    request = request_feature_promotion(
        "market_no_vig_home_win",
        "core_model",
        approved_by="model-governance-test",
        rationale="validated pre-match calibration and leakage checks",
    )

    assert request["from_bucket"] == "tracking_only"
    assert request["target_bucket"] == "core_model"
    assert request["status"] == "promotion_request_recorded_schema_not_mutated"
    assert "market_no_vig_home_win" in TRACKING_ONLY_FEATURES
    assert "market_no_vig_home_win" not in CORE_MODEL_FEATURES


def test_feature_schema_report_is_safe_and_complete() -> None:
    report = build_feature_schema_report()
    serialized = json.dumps(report)

    assert report["policy"]["feature_promotion_requires_schema"] is True
    assert report["policy"]["tracking_only_cannot_enter_model_directly"] is True
    assert report["bucket_counts"]["core_model"] == len(CORE_MODEL_FEATURES)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized
