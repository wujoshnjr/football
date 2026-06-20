from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable

from scripts.football_calibration_report import (
    MIN_SAMPLE_COUNT,
    OUTCOMES,
    as_float,
    as_probability,
    first_present,
    model_probabilities_from_row,
    round_metric,
    source_keys_from_row,
    stage_slice,
    utc_now,
)


MARKET_PROBABILITY_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("market_home_prob", "market_consensus_home_prob", "market_home_win_prob", "closing_market_home_prob"),
    "draw": ("market_draw_prob", "market_consensus_draw_prob", "market_draw_prob", "closing_market_draw_prob"),
    "away_win": ("market_away_prob", "market_consensus_away_prob", "market_away_win_prob", "closing_market_away_prob"),
}

MARKET_DECIMAL_ODDS_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("home_odds", "market_home_odds", "home_decimal_odds", "closing_home_odds"),
    "draw": ("draw_odds", "market_draw_odds", "draw_decimal_odds", "closing_draw_odds"),
    "away_win": ("away_odds", "market_away_odds", "away_decimal_odds", "closing_away_odds"),
}

OPENING_PROBABILITY_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("opening_market_home_prob", "open_market_home_prob", "opening_home_prob"),
    "draw": ("opening_market_draw_prob", "open_market_draw_prob", "opening_draw_prob"),
    "away_win": ("opening_market_away_prob", "open_market_away_prob", "opening_away_prob"),
}

CLOSING_PROBABILITY_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("closing_market_home_prob", "close_market_home_prob", "closing_home_prob"),
    "draw": ("closing_market_draw_prob", "close_market_draw_prob", "closing_draw_prob"),
    "away_win": ("closing_market_away_prob", "close_market_away_prob", "closing_away_prob"),
}

OPENING_DECIMAL_ODDS_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("opening_home_odds", "open_home_odds"),
    "draw": ("opening_draw_odds", "open_draw_odds"),
    "away_win": ("opening_away_odds", "open_away_odds"),
}

CLOSING_DECIMAL_ODDS_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("closing_home_odds", "close_home_odds"),
    "draw": ("closing_draw_odds", "close_draw_odds"),
    "away_win": ("closing_away_odds", "close_away_odds"),
}


def normalize_probability_triplet(values: dict[str, float | None]) -> dict[str, float] | None:
    parsed: dict[str, float] = {}
    for outcome in OUTCOMES:
        value = values.get(outcome)
        if value is None or value < 0.0:
            return None
        parsed[outcome] = value
    total = sum(parsed.values())
    if total <= 0.0 or not math.isfinite(total):
        return None
    return {outcome: parsed[outcome] / total for outcome in OUTCOMES}


def no_vig_1x2_from_decimal_odds(home: Any, draw: Any, away: Any) -> dict[str, float] | None:
    decimal_odds = {
        "home_win": as_float(home),
        "draw": as_float(draw),
        "away_win": as_float(away),
    }
    if any(value is None or value <= 1.0 for value in decimal_odds.values()):
        return None
    implied = {outcome: 1.0 / float(decimal_odds[outcome]) for outcome in OUTCOMES}
    return normalize_probability_triplet(implied)


def probabilities_from_fields(row: dict[str, Any], field_map: dict[str, tuple[str, ...]]) -> dict[str, float] | None:
    values = {outcome: as_probability(first_present(row, field_map[outcome])) for outcome in OUTCOMES}
    return normalize_probability_triplet(values)


def no_vig_from_odds_fields(row: dict[str, Any], field_map: dict[str, tuple[str, ...]]) -> dict[str, float] | None:
    return no_vig_1x2_from_decimal_odds(
        first_present(row, field_map["home_win"]),
        first_present(row, field_map["draw"]),
        first_present(row, field_map["away_win"]),
    )


def market_probabilities_from_row(row: dict[str, Any]) -> dict[str, float] | None:
    direct = probabilities_from_fields(row, MARKET_PROBABILITY_FIELDS)
    if direct is not None:
        return direct
    return no_vig_from_odds_fields(row, MARKET_DECIMAL_ODDS_FIELDS)


def opening_market_probabilities_from_row(row: dict[str, Any]) -> dict[str, float] | None:
    direct = probabilities_from_fields(row, OPENING_PROBABILITY_FIELDS)
    if direct is not None:
        return direct
    return no_vig_from_odds_fields(row, OPENING_DECIMAL_ODDS_FIELDS)


def closing_market_probabilities_from_row(row: dict[str, Any]) -> dict[str, float] | None:
    direct = probabilities_from_fields(row, CLOSING_PROBABILITY_FIELDS)
    if direct is not None:
        return direct
    return no_vig_from_odds_fields(row, CLOSING_DECIMAL_ODDS_FIELDS)


def favorite(probabilities: dict[str, float]) -> str:
    return max(OUTCOMES, key=lambda outcome: probabilities[outcome])


def market_movement_evidence(row: dict[str, Any]) -> dict[str, Any]:
    opening = opening_market_probabilities_from_row(row)
    closing = closing_market_probabilities_from_row(row)
    if opening is None or closing is None:
        return {
            "available": False,
            "role": "paper_tracking",
            "movement": {},
        }
    movement = {outcome: round_metric(closing[outcome] - opening[outcome]) for outcome in OUTCOMES}
    return {
        "available": True,
        "role": "paper_tracking",
        "opening_market_consensus": {outcome: round_metric(opening[outcome]) for outcome in OUTCOMES},
        "closing_market_consensus": {outcome: round_metric(closing[outcome]) for outcome in OUTCOMES},
        "movement": movement,
        "interpretation": "tracking_only_not_betting_advice",
    }


def comparison_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    comparisons: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    raw_count = 0
    for row in rows:
        raw_count += 1
        if not isinstance(row, dict):
            skipped["malformed_row"] = skipped.get("malformed_row", 0) + 1
            continue
        model = model_probabilities_from_row(row)
        if model is None:
            skipped["missing_or_invalid_model_probabilities"] = skipped.get("missing_or_invalid_model_probabilities", 0) + 1
            continue
        market = market_probabilities_from_row(row)
        if market is None:
            skipped["missing_or_invalid_market_consensus"] = skipped.get("missing_or_invalid_market_consensus", 0) + 1
            continue

        gap = {outcome: model[outcome] - market[outcome] for outcome in OUTCOMES}
        abs_gap = {outcome: abs(gap[outcome]) for outcome in OUTCOMES}
        market_favorite = favorite(market)
        model_favorite = favorite(model)
        comparisons.append(
            {
                "fixture_id": str(row.get("fixture_id") or row.get("id") or ""),
                "stage_slice": stage_slice(row),
                "source_keys": source_keys_from_row(row),
                "model_favorite": model_favorite,
                "market_favorite": market_favorite,
                "favorite_alignment": model_favorite == market_favorite,
                "model_probabilities": {outcome: round_metric(model[outcome]) for outcome in OUTCOMES},
                "market_consensus": {outcome: round_metric(market[outcome]) for outcome in OUTCOMES},
                "model_minus_market_gap": {outcome: round_metric(gap[outcome]) for outcome in OUTCOMES},
                "absolute_gap": {outcome: round_metric(abs_gap[outcome]) for outcome in OUTCOMES},
                "market_movement_evidence": market_movement_evidence(row),
            }
        )
    return comparisons, skipped, raw_count


def mean(values: Iterable[float]) -> float | None:
    data = list(values)
    if not data:
        return None
    return sum(data) / len(data)


def aggregate_gap_metrics(comparisons: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not comparisons:
        return None
    per_outcome = {}
    for outcome in OUTCOMES:
        signed = [float(item["model_minus_market_gap"][outcome]) for item in comparisons]
        absolute = [float(item["absolute_gap"][outcome]) for item in comparisons]
        per_outcome[outcome] = {
            "mean_model_minus_market_gap": round_metric(mean(signed)),
            "mean_absolute_gap": round_metric(mean(absolute)),
        }
    all_absolute = [float(item["absolute_gap"][outcome]) for item in comparisons for outcome in OUTCOMES]
    alignment_rate = mean(1.0 if item["favorite_alignment"] else 0.0 for item in comparisons)
    return {
        "mean_absolute_gap_all_outcomes": round_metric(mean(all_absolute)),
        "favorite_alignment_rate": round_metric(alignment_rate),
        "per_outcome": per_outcome,
    }


def stage_slices(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in comparisons:
        grouped.setdefault(item["stage_slice"], []).append(item)
    return {
        key: {
            "sample_count": len(value),
            "gap_metrics": aggregate_gap_metrics(value),
        }
        for key, value in sorted(grouped.items())
    }


def favorite_vs_underdog_slices(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    favorite_gaps: list[float] = []
    non_favorite_gaps: list[float] = []
    for item in comparisons:
        market_favorite = item["market_favorite"]
        for outcome in OUTCOMES:
            gap = float(item["model_minus_market_gap"][outcome])
            if outcome == market_favorite:
                favorite_gaps.append(gap)
            else:
                non_favorite_gaps.append(gap)
    return {
        "market_favorite": {
            "sample_count": len(favorite_gaps),
            "mean_model_minus_market_gap": round_metric(mean(favorite_gaps)),
        },
        "market_underdog_or_draw": {
            "sample_count": len(non_favorite_gaps),
            "mean_model_minus_market_gap": round_metric(mean(non_favorite_gaps)),
        },
    }


def market_movement_summary(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
    available = [item for item in comparisons if item["market_movement_evidence"].get("available")]
    if not available:
        return {
            "sample_count": 0,
            "role": "paper_tracking",
            "average_movement": {outcome: None for outcome in OUTCOMES},
        }
    return {
        "sample_count": len(available),
        "role": "paper_tracking",
        "average_movement": {
            outcome: round_metric(mean(float(item["market_movement_evidence"]["movement"][outcome]) for item in available))
            for outcome in OUTCOMES
        },
    }


def build_model_vs_market_report(
    rows: Iterable[dict[str, Any]],
    min_samples: int = MIN_SAMPLE_COUNT,
    include_rows: bool = False,
) -> dict[str, Any]:
    comparisons, skipped, raw_count = comparison_rows(rows)
    sample_count = len(comparisons)
    report: dict[str, Any] = {
        "report_type": "football_model_vs_market_report",
        "generated_at": utc_now(),
        "raw_row_count": raw_count,
        "sample_count": sample_count,
        "minimum_sample_count": min_samples,
        "status": "ok" if sample_count >= min_samples else "insufficient_sample",
        "signal_roles": ["market_consensus", "external_signal", "paper_tracking"],
        "skipped_count": sum(skipped.values()),
        "skipped_reasons": dict(sorted(skipped.items())),
        "gap_metrics": aggregate_gap_metrics(comparisons),
        "slices": {
            "stage": stage_slices(comparisons),
            "favorite_vs_underdog": favorite_vs_underdog_slices(comparisons),
        },
        "market_movement_evidence": market_movement_summary(comparisons),
        "source_provenance": {
            "missing_source_provenance_count": sum(1 for item in comparisons if not item["source_keys"]),
            "source_counts": source_counts(comparisons),
        },
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
            "betting_advice_allowed": False,
        },
        "notes": [
            "Market data is used only as market_consensus, external_signal, and paper_tracking evidence.",
            "This report does not create wagering instructions.",
        ],
    }
    if include_rows:
        report["comparisons"] = comparisons
    return report


def source_counts(comparisons: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in comparisons:
        for source in item.get("source_keys") or []:
            counts[source] = counts.get(source, 0) + 1
    return dict(sorted(counts.items()))


def write_model_vs_market_report(
    rows: Iterable[dict[str, Any]],
    output_path: Path = Path("report/model_vs_market_report.json"),
    min_samples: int = MIN_SAMPLE_COUNT,
) -> dict[str, Any]:
    report = build_model_vs_market_report(rows, min_samples=min_samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
    return report
