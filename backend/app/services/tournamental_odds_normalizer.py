from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

PROBABILITY_SUM_TOLERANCE = 0.03
SETTLED_LIKE_THRESHOLD = 0.995


def normalize_tournamental_snapshot(payload: Any) -> dict[str, Any]:
    data = payload.get("data", payload) if isinstance(payload, dict) else {}
    probabilities = data.get("probabilities", {}) if isinstance(data, dict) else {}
    if not isinstance(probabilities, dict):
        probabilities = {}

    match_markets: list[dict[str, Any]] = []
    group_markets: list[dict[str, Any]] = []
    winner_markets: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []

    for market_key, outcomes in probabilities.items():
        if not isinstance(market_key, str) or not isinstance(outcomes, dict):
            anomalies.append({"market_key": str(market_key), "reason": "invalid_market_shape"})
            continue

        if market_key.startswith("wc2026:match:"):
            record = normalize_match_market(market_key, outcomes)
            match_markets.append(record)
            if record["quality_flags"]:
                anomalies.append({
                    "market_key": market_key,
                    "market_type": "match",
                    "quality_flags": record["quality_flags"],
                    "probability_sum": record["probability_sum"],
                })
            continue

        if market_key.startswith("wc2026:group:"):
            group_markets.append(normalize_yes_no_market(market_key, outcomes, "group"))
            continue

        if market_key.startswith("wc2026:winner:"):
            winner_markets.append(normalize_yes_no_market(market_key, outcomes, "winner"))
            continue

        anomalies.append({"market_key": market_key, "reason": "unknown_market_type"})

    match_markets.sort(key=lambda item: numeric_sort_key(item.get("match_no")))
    group_markets.sort(key=lambda item: item.get("team_code") or "")
    winner_markets.sort(key=lambda item: item.get("team_code") or "")

    ts_ms = data.get("ts") if isinstance(data, dict) else None
    return {
        "source_key": payload.get("source_key", "tournamental_odds") if isinstance(payload, dict) else "tournamental_odds",
        "timestamp_ms": ts_ms,
        "timestamp_utc": timestamp_ms_to_iso(ts_ms),
        "market_count": data.get("market_count") if isinstance(data, dict) else None,
        "match_market_count": len(match_markets),
        "usable_match_market_count": sum(1 for item in match_markets if item["is_usable_for_prediction"]),
        "group_market_count": len(group_markets),
        "winner_market_count": len(winner_markets),
        "match_markets": match_markets,
        "group_markets": group_markets,
        "winner_markets": winner_markets,
        "anomalies": anomalies,
    }


def normalize_match_market(market_key: str, outcomes: dict[str, Any]) -> dict[str, Any]:
    normalized_outcomes = {str(name): safe_float(value) for name, value in outcomes.items()}
    normalized_outcomes = {name: value for name, value in normalized_outcomes.items() if value is not None}
    probability_sum = round(sum(normalized_outcomes.values()), 6)
    max_probability = max(normalized_outcomes.values(), default=0.0)
    flags: list[str] = []

    if len(normalized_outcomes) < 3:
        flags.append("too_few_outcomes")
    if probability_sum < 1 - PROBABILITY_SUM_TOLERANCE:
        flags.append("probability_sum_too_low")
    if probability_sum > 1 + PROBABILITY_SUM_TOLERANCE:
        flags.append("probability_sum_too_high")
    if max_probability >= SETTLED_LIKE_THRESHOLD:
        flags.append("settled_like")

    return {
        "market_key": market_key,
        "match_no": market_key.rsplit(":", 1)[-1],
        "outcomes": normalized_outcomes,
        "probability_sum": probability_sum,
        "max_probability": max_probability,
        "quality_flags": flags,
        "is_usable_for_prediction": not flags,
    }


def normalize_yes_no_market(market_key: str, outcomes: dict[str, Any], market_type: str) -> dict[str, Any]:
    yes_probability = safe_float(outcomes.get("Yes"))
    no_probability = safe_float(outcomes.get("No"))
    return {
        "market_key": market_key,
        "market_type": market_type,
        "team_code": market_key.rsplit(":", 1)[-1],
        "yes_probability": yes_probability,
        "no_probability": no_probability,
    }


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def numeric_sort_key(value: Any) -> tuple[int, str]:
    text = str(value or "")
    try:
        return int(text), text
    except ValueError:
        return 10**9, text


def timestamp_ms_to_iso(value: Any) -> str | None:
    numeric = safe_float(value)
    if numeric is None:
        return None
    return datetime.fromtimestamp(numeric / 1000, tz=timezone.utc).isoformat()
