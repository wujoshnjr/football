from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AdvancedFeature:
    key: str
    category: str
    description: str
    data_status: str
    model_use: str
    leakage_risk: str


def advanced_feature_registry() -> list[dict]:
    features = [
        AdvancedFeature(
            key="team_elo_strength",
            category="team_strength",
            description="Team-level rating feature used as a stable baseline for relative team quality.",
            data_status="available_baseline",
            model_use="Baseline probability and expected goals adjustment.",
            leakage_risk="low",
        ),
        AdvancedFeature(
            key="attack_defense_split",
            category="team_strength",
            description="Separate attacking and defensive strength estimates instead of a single team score.",
            data_status="planned_feature_table",
            model_use="Poisson goal-rate calibration and ensemble inputs.",
            leakage_risk="medium_if_post_match_stats_leak",
        ),
        AdvancedFeature(
            key="xg_xt_profile",
            category="advanced_metrics",
            description="Expected goals and expected threat profile built from event-level data when available.",
            data_status="requires_event_data",
            model_use="Shot quality, chance creation, and territorial threat signal.",
            leakage_risk="medium_if_future_events_leak",
        ),
        AdvancedFeature(
            key="player_availability_load",
            category="player_level",
            description="Player availability, minutes load, rest days, injury flags, and lineup stability.",
            data_status="requires_lineup_and_injury_sources",
            model_use="Adjust team strength when key players are absent or overloaded.",
            leakage_risk="medium_if_lineups_are_confirmed_after_prediction_cutoff",
        ),
        AdvancedFeature(
            key="referee_card_profile",
            category="causal_context",
            description="Referee foul and card tendency combined with team aggression and VAR context.",
            data_status="planned_feature_table",
            model_use="Red-card and penalty risk adjustment.",
            leakage_risk="low_if_referee_assigned_before_match",
        ),
        AdvancedFeature(
            key="environment_context",
            category="match_context",
            description="Altitude, temperature, humidity, travel distance, venue, and rest-day effects.",
            data_status="requires_weather_and_venue_sources",
            model_use="Fatigue, pace, and finishing-efficiency adjustment.",
            leakage_risk="low_if_weather_snapshot_is_pre_match",
        ),
        AdvancedFeature(
            key="market_consensus_signal",
            category="market_signal",
            description="Opening odds, closing odds, line movement, and bookmaker consensus when legally available.",
            data_status="requires_odds_source",
            model_use="External wisdom-of-crowds calibration and anomaly detection.",
            leakage_risk="medium_if_closing_odds_are_used_for_historical_training_without cutoff",
        ),
        AdvancedFeature(
            key="spatial_unpredictability_index",
            category="tactical_spatial",
            description="Proxy for how widely and unpredictably a team moves possession and attacking events across zones.",
            data_status="requires_event_or_tracking_data",
            model_use="Tactical diversity and transition threat signal.",
            leakage_risk="medium_if_current_match_events_leak",
        ),
        AdvancedFeature(
            key="video_micro_features",
            category="video_or_tracking",
            description="Future video-derived features such as defensive coverage, pressure shape, sprint count, and off-ball runs.",
            data_status="future_research",
            model_use="High-resolution tactical and physical signal.",
            leakage_risk="high_until_capture_time_is_strictly controlled",
        ),
        AdvancedFeature(
            key="bayesian_uncertainty_update",
            category="uncertainty",
            description="Bayesian-style uncertainty estimates and posterior updates for team strength and match context.",
            data_status="planned_model_layer",
            model_use="Prediction interval, confidence score, and conservative probability calibration.",
            leakage_risk="low",
        ),
        AdvancedFeature(
            key="ensemble_model_stack",
            category="modeling",
            description="Poisson, rating, tree-based, and calibrated meta-model stack for robust predictions.",
            data_status="planned_model_layer",
            model_use="Reduce single-model fragility and improve calibration.",
            leakage_risk="depends_on_input_features",
        ),
        AdvancedFeature(
            key="incremental_learning_guardrails",
            category="modeling",
            description="Controlled update process for transfers, tactical changes, rule changes, and new tournament evidence.",
            data_status="future_research",
            model_use="Model refresh without catastrophic forgetting.",
            leakage_risk="medium_if_updates_include future outcomes",
        ),
        AdvancedFeature(
            key="draw_probability_specialist",
            category="modeling",
            description="Dedicated draw calibration layer because draws are common and often under-modeled.",
            data_status="planned_model_layer",
            model_use="Improve 1X2 probability calibration, especially draw probability.",
            leakage_risk="low",
        ),
    ]
    return [asdict(feature) for feature in features]
