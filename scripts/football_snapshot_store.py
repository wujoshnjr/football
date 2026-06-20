from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PIPELINE_VERSION = "football_baseline_v1"
SNAPSHOT_POLICY = "first_seen_pregame"
SNAPSHOT_STORE_FILE = Path("data/prediction_snapshots.csv")
FINALIZED_FIXTURES_FILE = Path("data/finalized_fixtures.csv")

PREGAME_STATUSES = {"scheduled", "preview", "pre", "pregame", "not_started", "not started", "tbd"}
SETTLEMENT_COLUMNS = {"settled_at", "final_home_score", "final_away_score", "result", "advance_result", "settlement_status"}

SNAPSHOT_COLUMNS = [
    "snapshot_id",
    "pipeline_version",
    "snapshot_policy",
    "snapshot_created_at",
    "snapshot_valid",
    "snapshot_invalid_reason",
    "fixture_id",
    "kickoff_time",
    "fixture_status",
    "home_team",
    "away_team",
    "stage",
    "model_version",
    "model_source",
    "home_win_prob",
    "draw_prob",
    "away_win_prob",
    "predicted_outcome",
    "confidence",
    "feature_schema_hash",
    "features_json",
    "source_provenance_json",
    "live_betting_allowed",
    "automated_wagering_allowed",
    "real_money_betting_allowed",
    "settled_at",
    "final_home_score",
    "final_away_score",
    "result",
    "advance_result",
    "settlement_status",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc_iso(value: datetime | None = None) -> str:
    timestamp = (value or utc_now()).astimezone(timezone.utc)
    return timestamp.isoformat().replace("+00:00", "Z")


def parse_utc_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_fixture_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "none", "null", "nan"}:
        return ""
    return text


def snapshot_key(pipeline_version: str, fixture_id: Any) -> str:
    return f"{pipeline_version}:{normalize_fixture_id(fixture_id)}"


def stable_feature_schema_hash(feature_keys: Iterable[str]) -> str:
    payload = json.dumps(sorted(str(key) for key in feature_keys), separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def as_probability(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0.0 <= parsed <= 1.0 else None


def prediction_probabilities(prediction: dict[str, Any]) -> dict[str, float | None]:
    probabilities = prediction.get("probabilities")
    if not isinstance(probabilities, dict):
        probabilities = prediction
    return {
        "home_win": as_probability(probabilities.get("home_win")),
        "draw": as_probability(probabilities.get("draw")),
        "away_win": as_probability(probabilities.get("away_win")),
    }


def predicted_outcome(probabilities: dict[str, float | None]) -> str:
    if any(value is None for value in probabilities.values()):
        return ""
    return max(probabilities, key=lambda key: float(probabilities[key] or 0.0))


def validate_pregame_prediction(
    prediction: dict[str, Any],
    snapshot_created_at: datetime | None = None,
) -> tuple[bool, str]:
    observed_at = (snapshot_created_at or utc_now()).astimezone(timezone.utc)
    if not normalize_fixture_id(prediction.get("fixture_id") or prediction.get("id")):
        return False, "missing_fixture_id"

    kickoff_time = parse_utc_datetime(prediction.get("kickoff_time") or prediction.get("start_time"))
    if kickoff_time is None:
        return False, "missing_or_invalid_kickoff_time"
    if observed_at >= kickoff_time:
        return False, "snapshot_created_after_kickoff"

    status = str(prediction.get("status") or prediction.get("fixture_status") or "").strip().lower()
    if status not in PREGAME_STATUSES:
        return False, f"not_confirmed_pregame_status:{status or 'missing'}"

    probabilities = prediction_probabilities(prediction)
    if any(value is None for value in probabilities.values()):
        return False, "missing_or_invalid_1x2_probabilities"

    return True, ""


def build_snapshot_row(
    prediction: dict[str, Any],
    snapshot_created_at: datetime | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> dict[str, str]:
    observed_at = (snapshot_created_at or utc_now()).astimezone(timezone.utc)
    valid, invalid_reason = validate_pregame_prediction(prediction, snapshot_created_at=observed_at)
    fixture_id = normalize_fixture_id(prediction.get("fixture_id") or prediction.get("id"))
    probabilities = prediction_probabilities(prediction)
    features = prediction.get("features") if isinstance(prediction.get("features"), dict) else {}
    source_provenance = prediction.get("source_provenance") if isinstance(prediction.get("source_provenance"), list) else []

    row = {column: "" for column in SNAPSHOT_COLUMNS}
    row.update(
        {
            "snapshot_id": snapshot_key(pipeline_version, fixture_id),
            "pipeline_version": pipeline_version,
            "snapshot_policy": SNAPSHOT_POLICY,
            "snapshot_created_at": to_utc_iso(observed_at),
            "snapshot_valid": "true" if valid else "false",
            "snapshot_invalid_reason": invalid_reason,
            "fixture_id": fixture_id,
            "kickoff_time": stringify(prediction.get("kickoff_time") or prediction.get("start_time")),
            "fixture_status": stringify(prediction.get("status") or prediction.get("fixture_status")),
            "home_team": stringify(prediction.get("home_team")),
            "away_team": stringify(prediction.get("away_team")),
            "stage": stringify(prediction.get("stage")),
            "model_version": stringify(prediction.get("model_version")),
            "model_source": stringify(prediction.get("model_source") or "manual_baseline"),
            "home_win_prob": stringify(probabilities["home_win"]),
            "draw_prob": stringify(probabilities["draw"]),
            "away_win_prob": stringify(probabilities["away_win"]),
            "predicted_outcome": predicted_outcome(probabilities),
            "confidence": stringify(prediction.get("confidence")),
            "feature_schema_hash": stringify(prediction.get("feature_schema_hash") or stable_feature_schema_hash(features.keys())),
            "features_json": json.dumps(features, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
            "source_provenance_json": json.dumps(source_provenance, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
            "live_betting_allowed": "false",
            "automated_wagering_allowed": "false",
            "real_money_betting_allowed": "false",
            "settlement_status": "unsettled",
        }
    )
    return row


def read_snapshot_rows(path: Path = SNAPSHOT_STORE_FILE) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as file_obj:
        return [dict(row) for row in csv.DictReader(file_obj)]


def write_snapshot_rows(rows: list[dict[str, str]], path: Path = SNAPSHOT_STORE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=SNAPSHOT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in SNAPSHOT_COLUMNS})
    tmp_path.replace(path)


def append_first_seen_pregame_snapshots(
    predictions: Iterable[dict[str, Any]],
    path: Path = SNAPSHOT_STORE_FILE,
    snapshot_created_at: datetime | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> dict[str, Any]:
    observed_at = (snapshot_created_at or utc_now()).astimezone(timezone.utc)
    rows = read_snapshot_rows(path)
    existing = {snapshot_key(row.get("pipeline_version", ""), row.get("fixture_id", "")) for row in rows}
    total = 0
    inserted = 0
    duplicates = 0
    skipped: dict[str, int] = {}

    for prediction in predictions:
        total += 1
        if not isinstance(prediction, dict):
            skipped["malformed_prediction"] = skipped.get("malformed_prediction", 0) + 1
            continue

        row = build_snapshot_row(prediction, snapshot_created_at=observed_at, pipeline_version=pipeline_version)
        if row["snapshot_valid"] != "true":
            reason = row["snapshot_invalid_reason"] or "invalid"
            skipped[reason] = skipped.get(reason, 0) + 1
            continue

        if row["snapshot_id"] in existing:
            duplicates += 1
            continue

        rows.append(row)
        existing.add(row["snapshot_id"])
        inserted += 1

    if inserted:
        write_snapshot_rows(rows, path)

    return {
        "pipeline_version": pipeline_version,
        "snapshot_policy": SNAPSHOT_POLICY,
        "total_predictions": total,
        "inserted": inserted,
        "duplicates": duplicates,
        "skipped": skipped,
        "stored_rows": len(rows),
    }


def settle_snapshots(
    final_fixtures: Iterable[dict[str, Any]],
    path: Path = SNAPSHOT_STORE_FILE,
    settled_at: datetime | None = None,
    pipeline_version: str = PIPELINE_VERSION,
) -> dict[str, Any]:
    rows = read_snapshot_rows(path)
    if not rows:
        return {"pipeline_version": pipeline_version, "final_fixtures": 0, "updated": 0, "unmatched": 0, "stored_rows": 0}

    results: dict[str, dict[str, Any]] = {}
    for result in final_fixtures:
        if not isinstance(result, dict):
            continue
        fixture_id = normalize_fixture_id(result.get("fixture_id") or result.get("id"))
        if fixture_id:
            results[fixture_id] = result

    matched: set[str] = set()
    updated = 0
    settlement_time = to_utc_iso(settled_at)

    for row in rows:
        if row.get("pipeline_version") != pipeline_version:
            continue
        if row.get("snapshot_valid", "").lower() != "true":
            continue
        fixture_id = normalize_fixture_id(row.get("fixture_id"))
        result = results.get(fixture_id)
        if result is None:
            continue
        matched.add(fixture_id)
        if row.get("settlement_status") == "settled":
            continue

        try:
            home_score = int(result.get("home_score"))
            away_score = int(result.get("away_score"))
        except (TypeError, ValueError):
            continue

        row["settled_at"] = settlement_time
        row["final_home_score"] = str(home_score)
        row["final_away_score"] = str(away_score)
        row["result"] = stringify(result.get("result") or infer_1x2_result(home_score, away_score))
        row["advance_result"] = stringify(result.get("advance_result"))
        row["settlement_status"] = "settled"
        updated += 1

    if updated:
        write_snapshot_rows(rows, path)

    return {
        "pipeline_version": pipeline_version,
        "final_fixtures": len(results),
        "updated": updated,
        "unmatched": len(set(results) - matched),
        "stored_rows": len(rows),
    }


def infer_1x2_result(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return "home_win"
    if home_score < away_score:
        return "away_win"
    return "draw"
