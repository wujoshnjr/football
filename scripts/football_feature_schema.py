from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class FeatureSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    bucket: str
    category: str
    description: str
    allowed_use: str
    leakage_risk: str
    required_availability_flag: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def spec(
    key: str,
    bucket: str,
    category: str,
    description: str,
    allowed_use: str,
    leakage_risk: str,
    required_availability_flag: str | None = None,
) -> FeatureSpec:
    return FeatureSpec(
        key=key,
        bucket=bucket,
        category=category,
        description=description,
        allowed_use=allowed_use,
        leakage_risk=leakage_risk,
        required_availability_flag=required_availability_flag,
    )


CORE_MODEL_FEATURES: dict[str, FeatureSpec] = {
    feature.key: feature
    for feature in (
        spec("home_elo", "core_model", "team_strength", "Home team Elo-style rating before kickoff.", "active_model_input", "low"),
        spec("away_elo", "core_model", "team_strength", "Away team Elo-style rating before kickoff.", "active_model_input", "low"),
        spec("elo_diff", "core_model", "team_strength", "Home rating minus away rating.", "active_model_input", "low"),
        spec("home_recent_points_per_match", "core_model", "recent_form", "Home team recent points per match before cutoff.", "active_model_input", "medium_if_post_match_leak"),
        spec("away_recent_points_per_match", "core_model", "recent_form", "Away team recent points per match before cutoff.", "active_model_input", "medium_if_post_match_leak"),
        spec("recent_points_diff", "core_model", "recent_form", "Home recent points minus away recent points.", "active_model_input", "medium_if_post_match_leak"),
        spec("home_goals_for_per_match", "core_model", "goal_rate", "Home team pre-match goals-for rate.", "active_model_input", "medium_if_post_match_leak"),
        spec("away_goals_for_per_match", "core_model", "goal_rate", "Away team pre-match goals-for rate.", "active_model_input", "medium_if_post_match_leak"),
        spec("home_goals_against_per_match", "core_model", "goal_rate", "Home team pre-match goals-against rate.", "active_model_input", "medium_if_post_match_leak"),
        spec("away_goals_against_per_match", "core_model", "goal_rate", "Away team pre-match goals-against rate.", "active_model_input", "medium_if_post_match_leak"),
        spec("attack_defense_signal", "core_model", "goal_rate", "Simple attack-vs-defense differential from pre-match rates.", "active_model_input", "medium_if_post_match_leak"),
        spec("source_reliability_score", "core_model", "source_quality", "Configured source reliability score used as a conservative context adjustment.", "active_model_input", "low"),
        spec("fixture_consensus_score", "core_model", "source_quality", "Fixture-source consensus score from configured source context.", "active_model_input", "low"),
        spec("source_count", "core_model", "source_quality", "Count of active fixture-quality sources.", "active_model_input", "low"),
    )
}

TRACKING_ONLY_FEATURES: dict[str, FeatureSpec] = {
    feature.key: feature
    for feature in (
        spec("lineup_confirmed", "tracking_only", "lineup", "Whether a confirmed lineup is available before cutoff.", "tracking_only", "medium_cutoff_sensitive", "lineup_available"),
        spec("home_lineup_strength_delta", "tracking_only", "lineup", "Home lineup strength adjustment candidate.", "tracking_only", "medium_cutoff_sensitive", "lineup_available"),
        spec("away_lineup_strength_delta", "tracking_only", "lineup", "Away lineup strength adjustment candidate.", "tracking_only", "medium_cutoff_sensitive", "lineup_available"),
        spec("home_injury_count", "tracking_only", "injury", "Home unavailable player count from injury sources.", "tracking_only", "medium_source_quality", "injury_available"),
        spec("away_injury_count", "tracking_only", "injury", "Away unavailable player count from injury sources.", "tracking_only", "medium_source_quality", "injury_available"),
        spec("home_suspension_count", "tracking_only", "suspension", "Home suspended player count.", "tracking_only", "medium_source_quality", "suspension_available"),
        spec("away_suspension_count", "tracking_only", "suspension", "Away suspended player count.", "tracking_only", "medium_source_quality", "suspension_available"),
        spec("home_xg_for", "tracking_only", "xg", "Home expected-goals-for candidate feature.", "tracking_only", "medium_sample_and_source_quality", "xg_available"),
        spec("away_xg_for", "tracking_only", "xg", "Away expected-goals-for candidate feature.", "tracking_only", "medium_sample_and_source_quality", "xg_available"),
        spec("home_xg_against", "tracking_only", "xg", "Home expected-goals-against candidate feature.", "tracking_only", "medium_sample_and_source_quality", "xg_available"),
        spec("away_xg_against", "tracking_only", "xg", "Away expected-goals-against candidate feature.", "tracking_only", "medium_sample_and_source_quality", "xg_available"),
        spec("market_no_vig_home_win", "tracking_only", "market_consensus", "No-vig market-implied home-win probability.", "market_consensus_tracking_only", "medium_cutoff_sensitive", "odds_available"),
        spec("market_no_vig_draw", "tracking_only", "market_consensus", "No-vig market-implied draw probability.", "market_consensus_tracking_only", "medium_cutoff_sensitive", "odds_available"),
        spec("market_no_vig_away_win", "tracking_only", "market_consensus", "No-vig market-implied away-win probability.", "market_consensus_tracking_only", "medium_cutoff_sensitive", "odds_available"),
        spec("market_movement_home", "tracking_only", "paper_tracking", "Pre-match market movement for home outcome.", "paper_tracking", "medium_cutoff_sensitive", "odds_available"),
        spec("weather_temperature_c", "tracking_only", "weather", "Venue temperature near kickoff.", "tracking_only", "low_if_pre_match_snapshot", "weather_available"),
        spec("weather_wind_kph", "tracking_only", "weather", "Venue wind speed near kickoff.", "tracking_only", "low_if_pre_match_snapshot", "weather_available"),
        spec("weather_precipitation_mm", "tracking_only", "weather", "Venue precipitation near kickoff.", "tracking_only", "low_if_pre_match_snapshot", "weather_available"),
        spec("home_news_alert_count", "tracking_only", "news", "Home team qualitative alert count.", "tracking_only", "medium_unstructured_source", "news_available"),
        spec("away_news_alert_count", "tracking_only", "news", "Away team qualitative alert count.", "tracking_only", "medium_unstructured_source", "news_available"),
        spec("tournamental_market_gap_home", "tracking_only", "external_signal", "Tournamental home probability gap candidate.", "external_signal_tracking_only", "medium_external_benchmark", "odds_available"),
        spec("tournamental_market_gap_draw", "tracking_only", "external_signal", "Tournamental draw probability gap candidate.", "external_signal_tracking_only", "medium_external_benchmark", "odds_available"),
        spec("tournamental_market_gap_away", "tracking_only", "external_signal", "Tournamental away probability gap candidate.", "external_signal_tracking_only", "medium_external_benchmark", "odds_available"),
        spec("tournamental_injury_signal", "tracking_only", "external_signal", "Tournamental read-only injury signal candidate.", "external_signal_tracking_only", "medium_external_benchmark", "injury_available"),
        spec("tournamental_weather_signal", "tracking_only", "external_signal", "Tournamental read-only weather signal candidate.", "external_signal_tracking_only", "medium_external_benchmark", "weather_available"),
    )
}

AVAILABILITY_FLAG_FEATURES: dict[str, FeatureSpec] = {
    feature.key: feature
    for feature in (
        spec("fixture_available", "availability_flag", "availability", "Fixture source was available before prediction cutoff.", "availability_flag", "low"),
        spec("odds_available", "availability_flag", "availability", "Market-consensus or paper odds signal was available before cutoff.", "availability_flag", "low"),
        spec("lineup_available", "availability_flag", "availability", "Lineup data was available before cutoff.", "availability_flag", "low"),
        spec("injury_available", "availability_flag", "availability", "Injury data was available before cutoff.", "availability_flag", "low"),
        spec("suspension_available", "availability_flag", "availability", "Suspension data was available before cutoff.", "availability_flag", "low"),
        spec("weather_available", "availability_flag", "availability", "Weather data was available before cutoff.", "availability_flag", "low"),
        spec("fifa_ranking_available", "availability_flag", "availability", "FIFA ranking snapshot was available before cutoff.", "availability_flag", "low"),
        spec("xg_available", "availability_flag", "availability", "xG source was available before cutoff.", "availability_flag", "low"),
        spec("news_available", "availability_flag", "availability", "News source was available before cutoff.", "availability_flag", "low"),
    )
}

SHADOW_CANDIDATE_FEATURES: dict[str, FeatureSpec] = {
    feature.key: feature
    for feature in (
        spec("draw_probability_specialist_signal", "shadow_candidate", "modeling", "Candidate draw-calibration signal.", "shadow_only", "low"),
        spec("bayesian_team_strength_delta", "shadow_candidate", "uncertainty", "Bayesian team-strength update candidate.", "shadow_only", "medium_training_process"),
        spec("spatial_unpredictability_index", "shadow_candidate", "tactical_spatial", "Event/tracking-derived tactical diversity proxy.", "shadow_only", "medium_event_timing"),
        spec("referee_card_profile", "shadow_candidate", "causal_context", "Referee card tendency candidate feature.", "shadow_only", "low_if_pre_match_assignment"),
        spec("travel_fatigue_index", "shadow_candidate", "match_context", "Travel, rest, and timezone fatigue candidate.", "shadow_only", "medium_data_quality"),
        spec("tournamental_bot_consensus_gap", "shadow_candidate", "external_signal", "Bot-arena benchmark gap candidate.", "shadow_only", "medium_external_benchmark"),
        spec("ensemble_stack_shadow_probability", "shadow_candidate", "modeling", "Shadow ensemble probability candidate.", "shadow_only", "medium_model_governance"),
    )
}

FEATURE_BUCKETS: Mapping[str, dict[str, FeatureSpec]] = {
    "core_model": CORE_MODEL_FEATURES,
    "tracking_only": TRACKING_ONLY_FEATURES,
    "availability_flag": AVAILABILITY_FLAG_FEATURES,
    "shadow_candidate": SHADOW_CANDIDATE_FEATURES,
}


def all_feature_specs() -> dict[str, FeatureSpec]:
    features: dict[str, FeatureSpec] = {}
    for bucket in FEATURE_BUCKETS.values():
        overlap = set(features).intersection(bucket)
        if overlap:
            raise FeatureSchemaError(f"duplicate feature keys: {sorted(overlap)}")
        features.update(bucket)
    return features


def feature_bucket(feature_key: str) -> str:
    for bucket_name, bucket in FEATURE_BUCKETS.items():
        if feature_key in bucket:
            return bucket_name
    raise FeatureSchemaError(f"unknown feature: {feature_key}")


def assert_core_model_features(feature_keys: list[str] | tuple[str, ...] | set[str]) -> None:
    unknown = [key for key in feature_keys if key not in all_feature_specs()]
    if unknown:
        raise FeatureSchemaError(f"unknown features cannot enter core model: {unknown}")

    blocked = [key for key in feature_keys if key not in CORE_MODEL_FEATURES]
    if blocked:
        raise FeatureSchemaError(f"non-core features cannot enter core model without promotion: {blocked}")


def request_feature_promotion(
    feature_key: str,
    target_bucket: str,
    *,
    approved_by: str | None = None,
    rationale: str | None = None,
) -> dict[str, Any]:
    current_bucket = feature_bucket(feature_key)
    if target_bucket not in FEATURE_BUCKETS:
        raise FeatureSchemaError(f"unknown target bucket: {target_bucket}")
    if current_bucket == target_bucket:
        raise FeatureSchemaError(f"feature already belongs to {target_bucket}: {feature_key}")
    if not approved_by or not rationale:
        raise FeatureSchemaError("feature promotion requires approved_by and rationale")

    return {
        "feature_key": feature_key,
        "from_bucket": current_bucket,
        "target_bucket": target_bucket,
        "approved_by": approved_by,
        "rationale": rationale,
        "status": "promotion_request_recorded_schema_not_mutated",
    }


def build_feature_schema_report() -> dict[str, Any]:
    return {
        "bucket_counts": {bucket_name: len(bucket) for bucket_name, bucket in FEATURE_BUCKETS.items()},
        "core_model_features": sorted(CORE_MODEL_FEATURES),
        "tracking_only_features": sorted(TRACKING_ONLY_FEATURES),
        "availability_flag_features": sorted(AVAILABILITY_FLAG_FEATURES),
        "shadow_candidate_features": sorted(SHADOW_CANDIDATE_FEATURES),
        "features": {key: spec.to_dict() for key, spec in sorted(all_feature_specs().items())},
        "policy": {
            "feature_promotion_requires_schema": True,
            "tracking_only_cannot_enter_model_directly": True,
            "availability_flags_are_not_strength_features": True,
            "market_data_roles": ["market_consensus", "external_signal", "paper_tracking"],
        },
    }
