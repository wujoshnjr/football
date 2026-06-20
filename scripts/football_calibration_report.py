from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


OUTCOMES: tuple[str, ...] = ("home_win", "draw", "away_win")
MIN_SAMPLE_COUNT = 30

MODEL_PROBABILITY_FIELDS: dict[str, tuple[str, ...]] = {
    "home_win": ("model_home_prob", "home_win_prob", "home_prob", "prob_home_win", "home_win_probability"),
    "draw": ("model_draw_prob", "draw_prob", "prob_draw", "draw_probability"),
    "away_win": ("model_away_prob", "away_win_prob", "away_prob", "prob_away_win", "away_win_probability"),
}

ACTUAL_RESULT_FIELDS: tuple[str, ...] = (
    "actual_result",
    "actual_outcome",
    "result",
    "regulation_result",
    "settled_result",
)

HOME_SCORE_FIELDS: tuple[str, ...] = ("final_home_score", "home_score", "home_goals", "home_team_score")
AWAY_SCORE_FIELDS: tuple[str, ...] = ("final_away_score", "away_score", "away_goals", "away_team_score")

GROUP_STAGE_MARKERS = {"group", "group_stage", "group stage"}
KNOCKOUT_STAGE_MARKERS = {
    "round_of_16",
    "round of 16",
    "last_16",
    "last 16",
    "knockout",
    "quarterfinal",
    "quarter-final",
    "quarter final",
    "semifinal",
    "semi-final",
    "semi final",
    "final",
    "third_place",
    "third place",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def round_metric(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def as_probability(value: Any) -> float | None:
    parsed = as_float(value)
    if parsed is None:
        return None
    if 0.0 <= parsed <= 1.0:
        return parsed
    if 1.0 < parsed <= 100.0:
        return parsed / 100.0
    return None


def first_present(row: dict[str, Any], fields: Iterable[str]) -> Any:
    for field in fields:
        value = row.get(field)
        if value is not None and str(value).strip() != "":
            return value
    return None


def normalize_outcome(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "home": "home_win",
        "h": "home_win",
        "home_win": "home_win",
        "home_wins": "home_win",
        "1": "home_win",
        "draw": "draw",
        "d": "draw",
        "tie": "draw",
        "x": "draw",
        "0": "draw",
        "away": "away_win",
        "a": "away_win",
        "away_win": "away_win",
        "away_wins": "away_win",
        "2": "away_win",
    }
    return aliases.get(normalized)


def score_value(row: dict[str, Any], fields: Iterable[str]) -> int | None:
    value = first_present(row, fields)
    parsed = as_float(value)
    if parsed is None or not parsed.is_integer():
        return None
    return int(parsed)


def actual_outcome_from_row(row: dict[str, Any]) -> str | None:
    direct = normalize_outcome(first_present(row, ACTUAL_RESULT_FIELDS))
    if direct:
        return direct
    home_score = score_value(row, HOME_SCORE_FIELDS)
    away_score = score_value(row, AWAY_SCORE_FIELDS)
    if home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return "home_win"
    if home_score < away_score:
        return "away_win"
    return "draw"


def normalize_probabilities(probabilities: dict[str, float | None]) -> dict[str, float] | None:
    values: dict[str, float] = {}
    for outcome in OUTCOMES:
        value = probabilities.get(outcome)
        if value is None or value < 0.0:
            return None
        values[outcome] = value
    total = sum(values.values())
    if total <= 0.0 or not math.isfinite(total):
        return None
    return {outcome: values[outcome] / total for outcome in OUTCOMES}


def model_probabilities_from_row(row: dict[str, Any]) -> dict[str, float] | None:
    nested = row.get("model_probabilities") or row.get("probabilities")
    if isinstance(nested, dict):
        nested_values = {outcome: as_probability(nested.get(outcome)) for outcome in OUTCOMES}
        normalized = normalize_probabilities(nested_values)
        if normalized is not None:
            return normalized

    values = {
        outcome: as_probability(first_present(row, MODEL_PROBABILITY_FIELDS[outcome]))
        for outcome in OUTCOMES
    }
    return normalize_probabilities(values)


def stage_slice(row: dict[str, Any]) -> str:
    stage = str(row.get("stage") or row.get("round") or row.get("phase") or "").strip().lower()
    normalized = stage.replace("-", "_").replace(" ", "_")
    if any(marker.replace(" ", "_").replace("-", "_") in normalized for marker in GROUP_STAGE_MARKERS):
        return "group_stage"
    if any(marker.replace(" ", "_").replace("-", "_") in normalized for marker in KNOCKOUT_STAGE_MARKERS):
        return "knockout"
    return "unknown_stage"


def prediction_favorite(probabilities: dict[str, float]) -> str:
    return max(OUTCOMES, key=lambda outcome: probabilities[outcome])


def favorite_slice(prepared_row: dict[str, Any]) -> str:
    favorite = prediction_favorite(prepared_row["model_probabilities"])
    return "favorite_result" if prepared_row.get("actual_outcome") == favorite else "underdog_or_draw_result"


def source_keys_from_row(row: dict[str, Any]) -> list[str]:
    provenance = row.get("source_provenance") or row.get("source_snapshot") or row.get("sources")
    sources: list[str] = []
    if isinstance(provenance, list):
        for item in provenance:
            if isinstance(item, dict):
                key = item.get("source") or item.get("source_key") or item.get("key")
                if key:
                    sources.append(str(key))
            elif item:
                sources.append(str(item))
    elif isinstance(provenance, dict):
        for key, value in provenance.items():
            if value:
                sources.append(str(key))
    elif row.get("source"):
        sources.append(str(row["source"]))
    return sorted(set(sources))


def source_provenance_summary(prepared_rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    missing = 0
    for item in prepared_rows:
        sources = item.get("source_keys") or []
        if not sources:
            missing += 1
        for source in sources:
            counts[source] = counts.get(source, 0) + 1
    return {
        "source_counts": dict(sorted(counts.items())),
        "missing_source_provenance_count": missing,
    }


def prepare_evaluation_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int], int]:
    prepared: list[dict[str, Any]] = []
    skipped: dict[str, int] = {}
    raw_count = 0
    for row in rows:
        raw_count += 1
        if not isinstance(row, dict):
            skipped["malformed_row"] = skipped.get("malformed_row", 0) + 1
            continue
        probabilities = model_probabilities_from_row(row)
        if probabilities is None:
            skipped["missing_or_invalid_model_probabilities"] = skipped.get("missing_or_invalid_model_probabilities", 0) + 1
            continue
        actual = actual_outcome_from_row(row)
        if actual not in OUTCOMES:
            skipped["missing_or_invalid_actual_outcome"] = skipped.get("missing_or_invalid_actual_outcome", 0) + 1
            continue
        prepared.append(
            {
                "fixture_id": str(row.get("fixture_id") or row.get("id") or ""),
                "stage_slice": stage_slice(row),
                "actual_outcome": actual,
                "model_probabilities": probabilities,
                "favorite_slice": favorite_slice({"actual_outcome": actual, "model_probabilities": probabilities}),
                "source_keys": source_keys_from_row(row),
                "raw": row,
            }
        )
    return prepared, skipped, raw_count


def multiclass_brier_score(rows: Iterable[dict[str, Any]]) -> float | None:
    prepared, _, _ = prepare_evaluation_rows(rows)
    if not prepared:
        return None
    total = 0.0
    for item in prepared:
        actual = item["actual_outcome"]
        probabilities = item["model_probabilities"]
        total += sum((probabilities[outcome] - (1.0 if outcome == actual else 0.0)) ** 2 for outcome in OUTCOMES)
    return total / len(prepared)


def multiclass_log_loss(rows: Iterable[dict[str, Any]], epsilon: float = 1e-15) -> float | None:
    prepared, _, _ = prepare_evaluation_rows(rows)
    if not prepared:
        return None
    total = 0.0
    for item in prepared:
        probability = item["model_probabilities"][item["actual_outcome"]]
        clipped = min(max(probability, epsilon), 1.0 - epsilon)
        total += -math.log(clipped)
    return total / len(prepared)


def calibration_bins(prepared_rows: Iterable[dict[str, Any]], outcome: str, bin_count: int = 5) -> list[dict[str, Any]]:
    if outcome not in OUTCOMES:
        raise ValueError(f"Unsupported outcome: {outcome}")
    bin_count = max(int(bin_count), 1)
    bins: list[dict[str, Any]] = []
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        bins.append(
            {
                "bin": index,
                "lower_bound": round_metric(lower),
                "upper_bound": round_metric(upper),
                "sample_count": 0,
                "avg_predicted_probability": None,
                "observed_frequency": None,
            }
        )

    bucket_values: list[list[tuple[float, int]]] = [[] for _ in range(bin_count)]
    for item in prepared_rows:
        probability = item["model_probabilities"][outcome]
        index = min(int(probability * bin_count), bin_count - 1)
        observed = 1 if item["actual_outcome"] == outcome else 0
        bucket_values[index].append((probability, observed))

    for index, values in enumerate(bucket_values):
        if not values:
            continue
        sample_count = len(values)
        bins[index]["sample_count"] = sample_count
        bins[index]["avg_predicted_probability"] = round_metric(sum(value[0] for value in values) / sample_count)
        bins[index]["observed_frequency"] = round_metric(sum(value[1] for value in values) / sample_count)
    return bins


def metric_summary(prepared_rows: Iterable[dict[str, Any]], min_samples: int = MIN_SAMPLE_COUNT) -> dict[str, Any]:
    sample = list(prepared_rows)
    sample_count = len(sample)
    if not sample:
        return {
            "sample_count": 0,
            "minimum_sample_count": min_samples,
            "status": "insufficient_sample",
            "metrics": None,
        }

    brier_total = 0.0
    logloss_total = 0.0
    for item in sample:
        actual = item["actual_outcome"]
        probabilities = item["model_probabilities"]
        brier_total += sum((probabilities[outcome] - (1.0 if outcome == actual else 0.0)) ** 2 for outcome in OUTCOMES)
        logloss_total += -math.log(min(max(probabilities[actual], 1e-15), 1.0 - 1e-15))

    return {
        "sample_count": sample_count,
        "minimum_sample_count": min_samples,
        "status": "ok" if sample_count >= min_samples else "insufficient_sample",
        "metrics": {
            "multiclass_brier_score": round_metric(brier_total / sample_count),
            "multiclass_log_loss": round_metric(logloss_total / sample_count),
        },
    }


def grouped_summary(prepared_rows: list[dict[str, Any]], group_field: str, min_samples: int) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in prepared_rows:
        key = str(item.get(group_field) or "unknown")
        grouped.setdefault(key, []).append(item)
    return {key: metric_summary(value, min_samples=min_samples) for key, value in sorted(grouped.items())}


def build_calibration_report(
    rows: Iterable[dict[str, Any]],
    min_samples: int = MIN_SAMPLE_COUNT,
    bin_count: int = 5,
) -> dict[str, Any]:
    prepared, skipped, raw_count = prepare_evaluation_rows(rows)
    sample_count = len(prepared)
    return {
        "report_type": "football_calibration_report",
        "generated_at": utc_now(),
        "raw_row_count": raw_count,
        "sample_count": sample_count,
        "minimum_sample_count": min_samples,
        "status": "ok" if sample_count >= min_samples else "insufficient_sample",
        "outcomes": list(OUTCOMES),
        "skipped_count": sum(skipped.values()),
        "skipped_reasons": dict(sorted(skipped.items())),
        "metrics": metric_summary(prepared, min_samples=min_samples)["metrics"],
        "calibration": {
            outcome: calibration_bins(prepared, outcome=outcome, bin_count=bin_count)
            for outcome in OUTCOMES
        },
        "slices": {
            "stage": grouped_summary(prepared, "stage_slice", min_samples=min_samples),
            "favorite_vs_underdog": grouped_summary(prepared, "favorite_slice", min_samples=min_samples),
        },
        "source_provenance": source_provenance_summary(prepared),
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
            "betting_advice_allowed": False,
        },
        "notes": [
            "Evaluation is retrospective and paper-only.",
            "Low sample counts are reported as insufficient_sample and must not be treated as production proof.",
        ],
    }


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("predictions", "rows", "samples", "fixtures"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def write_calibration_report(
    rows: Iterable[dict[str, Any]],
    output_path: Path = Path("report/calibration_report.json"),
    min_samples: int = MIN_SAMPLE_COUNT,
) -> dict[str, Any]:
    report = build_calibration_report(rows, min_samples=min_samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
    return report
