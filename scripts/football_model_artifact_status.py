from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from scripts.football_feature_schema import CORE_MODEL_FEATURES
except Exception:  # pragma: no cover - keeps status generation non-crashing in partial installs
    CORE_MODEL_FEATURES = {}


MODEL_SOURCES: tuple[str, ...] = ("manual_baseline", "trained_artifact", "shadow_model")
MIN_CLEAN_TRAIN_SAMPLES = 300
MIN_PRODUCTION_SAMPLES = 1000

DEFAULT_ARTIFACT_PATH = Path("data/models/football_model_artifact.json")
DEFAULT_TRAINING_STATUS_PATH = Path("data/training_status.json")
DEFAULT_PREDICTION_SNAPSHOTS_PATH = Path("data/prediction_snapshots.csv")
DEFAULT_OUTPUT_PATH = Path("data/model_artifact_status.json")
DEFAULT_REPORT_PATH = Path("report/model_artifact_status_report.json")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Mapping):
        return {str(key): json_safe(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(child) for child in value]
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def read_json_object(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    status = {"path": str(path), "exists": path.exists(), "error": ""}
    if not path.exists():
        status["error"] = "file_missing"
        return {}, status
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - status reports errors instead of crashing
        status["error"] = str(exc)
        return {}, status
    if not isinstance(payload, dict):
        status["error"] = "json_not_object"
        return {}, status
    return payload, status


def safe_int(value: Any, default: int = 0) -> int:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        return default
    return int(parsed)


def count_csv_rows(path: Path) -> tuple[int | None, dict[str, Any]]:
    status = {"path": str(path), "exists": path.exists(), "rows": None, "error": ""}
    if not path.exists():
        status["error"] = "file_missing"
        return None, status
    try:
        with path.open("r", newline="", encoding="utf-8") as file_obj:
            reader = csv.reader(file_obj)
            try:
                next(reader)
            except StopIteration:
                status["rows"] = 0
                return 0, status
            row_count = sum(1 for _ in reader)
    except Exception as exc:  # noqa: BLE001 - status reports errors instead of crashing
        status["error"] = str(exc)
        return None, status
    status["rows"] = row_count
    return row_count, status


def current_feature_schema_hash() -> str:
    feature_keys = sorted(str(key) for key in CORE_MODEL_FEATURES)
    payload = json.dumps(feature_keys, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def normalize_model_source(value: Any, artifact_exists: bool, artifact_loadable: bool) -> tuple[str, str]:
    raw = str(value or "").strip()
    if raw in MODEL_SOURCES:
        return raw, ""
    if artifact_exists and artifact_loadable and not raw:
        return "trained_artifact", ""
    if raw:
        return "manual_baseline", "invalid_model_source"
    return "manual_baseline", "artifact_missing_or_unloadable"


def first_int(*values: Any, default: int = 0) -> int:
    for value in values:
        parsed = safe_int(value, default=-1)
        if parsed >= 0:
            return parsed
    return default


def build_model_artifact_status(
    artifact_path: Path = DEFAULT_ARTIFACT_PATH,
    training_status_path: Path = DEFAULT_TRAINING_STATUS_PATH,
    prediction_snapshots_path: Path = DEFAULT_PREDICTION_SNAPSHOTS_PATH,
    output_path: Path | None = DEFAULT_OUTPUT_PATH,
    report_path: Path | None = DEFAULT_REPORT_PATH,
    min_clean_train_samples: int = MIN_CLEAN_TRAIN_SAMPLES,
    min_production_samples: int = MIN_PRODUCTION_SAMPLES,
) -> dict[str, Any]:
    artifact, artifact_file = read_json_object(artifact_path)
    training_status, training_status_file = read_json_object(training_status_path)
    snapshot_row_count, snapshot_file = count_csv_rows(prediction_snapshots_path)

    artifact_exists = bool(artifact_file["exists"])
    artifact_loadable = artifact_exists and not artifact_file["error"]
    model_source, source_reason = normalize_model_source(artifact.get("model_source"), artifact_exists, artifact_loadable)

    expected_hash = current_feature_schema_hash()
    artifact_hash = str(artifact.get("feature_schema_hash") or training_status.get("feature_schema_hash") or "")
    feature_schema_match = bool(artifact_hash) and artifact_hash == expected_hash

    clean_train_samples = first_int(
        artifact.get("clean_train_samples"),
        artifact.get("training_sample_count"),
        training_status.get("clean_train_samples"),
        training_status.get("train_eligible_samples"),
        training_status.get("sample_count"),
        snapshot_row_count,
        default=0,
    )
    production_samples = first_int(
        artifact.get("production_samples"),
        training_status.get("production_samples"),
        training_status.get("settled_predictions"),
        snapshot_row_count,
        default=0,
    )

    blockers: list[str] = []
    if not artifact_exists:
        blockers.append("artifact_missing")
    elif not artifact_loadable:
        blockers.append("artifact_unloadable")
    if source_reason:
        blockers.append(source_reason)
    if model_source not in MODEL_SOURCES:
        blockers.append("model_source_not_allowed")
    if model_source == "manual_baseline":
        blockers.append("manual_baseline_fallback_not_production_artifact")
    if clean_train_samples < min_clean_train_samples:
        blockers.append("clean_train_samples_below_minimum")
    if production_samples < min_production_samples:
        blockers.append("production_samples_below_minimum")
    if not feature_schema_match:
        blockers.append("feature_schema_hash_mismatch")

    active_model_allowed = (
        model_source == "trained_artifact"
        and artifact_loadable
        and clean_train_samples >= min_clean_train_samples
        and feature_schema_match
    )
    production_ready = active_model_allowed and production_samples >= min_production_samples

    report = {
        "report_type": "football_model_artifact_status",
        "generated_at": utc_now(),
        "status": "ok" if active_model_allowed else "fallback_manual_baseline",
        "artifact_file": artifact_file,
        "training_status_file": training_status_file,
        "prediction_snapshots_file": snapshot_file,
        "artifact_exists": artifact_exists,
        "artifact_loadable": artifact_loadable,
        "model_source": model_source,
        "allowed_model_sources": list(MODEL_SOURCES),
        "fallback_model_source": "manual_baseline" if not active_model_allowed else None,
        "active_model_allowed": active_model_allowed,
        "production_ready": production_ready,
        "clean_train_samples": clean_train_samples,
        "minimum_clean_train_samples": min_clean_train_samples,
        "production_samples": production_samples,
        "minimum_production_samples": min_production_samples,
        "feature_schema_hash": expected_hash,
        "artifact_feature_schema_hash": artifact_hash,
        "feature_schema_match": feature_schema_match,
        "blockers": blockers,
        "metadata": artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {},
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
            "production_deploy_allowed": False,
        },
    }

    if output_path is not None:
        write_json(output_path, report)
    if report_path is not None:
        write_json(report_path, report)
    return report
