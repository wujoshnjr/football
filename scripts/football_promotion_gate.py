from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scripts.football_model_artifact_status import MODEL_SOURCES, current_feature_schema_hash, json_safe, safe_int, write_json


MIN_CLEAN_TRAIN_SAMPLES = 300
MIN_SETTLED_PREDICTIONS = 500
MIN_PRODUCTION_SAMPLES = 1000

DEFAULT_MODEL_STATUS_PATH = Path("data/model_artifact_status.json")
DEFAULT_CALIBRATION_REPORT_PATH = Path("report/calibration_report.json")
DEFAULT_SAMPLE_STATE_PATH = Path("data/sample_state.json")
DEFAULT_DATA_CONTRACT_PATH = Path("report/data_contract_report.json")
DEFAULT_OUTPUT_PATH = Path("report/promotion_gate_report.json")

LOCKED_SAFETY_FLAGS: tuple[str, ...] = (
    "live_betting_allowed",
    "automated_wagering_allowed",
    "real_money_betting_allowed",
    "pick_submission_allowed",
    "production_deploy_allowed",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json_object(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    status = {"path": str(path), "exists": path.exists(), "error": ""}
    if not path.exists():
        status["error"] = "file_missing"
        return {}, status
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - promotion gate records errors instead of crashing
        status["error"] = str(exc)
        return {}, status
    if not isinstance(payload, dict):
        status["error"] = "json_not_object"
        return {}, status
    return payload, status


def first_int(*values: Any, default: int = 0) -> int:
    for value in values:
        parsed = safe_int(value, default=-1)
        if parsed >= 0:
            return parsed
    return default


def as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return None


def finite_or_none(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def report_flag(report: Mapping[str, Any], flag: str) -> bool | None:
    direct = as_bool(report.get(flag))
    if direct is not None:
        return direct
    safety = report.get("safety")
    if isinstance(safety, Mapping):
        return as_bool(safety.get(flag))
    return None


def safety_blockers(*reports: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for flag in LOCKED_SAFETY_FLAGS:
        for report in reports:
            if report_flag(report, flag) is True:
                blockers.append(f"{flag}_must_be_false")
                break
    return blockers


def normalize_model_source(value: Any) -> str:
    text = str(value or "manual_baseline").strip()
    return text if text in MODEL_SOURCES else "manual_baseline"


def build_promotion_gate_report(
    model_status: Mapping[str, Any] | None = None,
    calibration_report: Mapping[str, Any] | None = None,
    sample_state: Mapping[str, Any] | None = None,
    data_contract_report: Mapping[str, Any] | None = None,
    model_status_path: Path = DEFAULT_MODEL_STATUS_PATH,
    calibration_report_path: Path = DEFAULT_CALIBRATION_REPORT_PATH,
    sample_state_path: Path = DEFAULT_SAMPLE_STATE_PATH,
    data_contract_path: Path = DEFAULT_DATA_CONTRACT_PATH,
    output_path: Path | None = DEFAULT_OUTPUT_PATH,
    min_clean_train_samples: int = MIN_CLEAN_TRAIN_SAMPLES,
    min_settled_predictions: int = MIN_SETTLED_PREDICTIONS,
    min_production_samples: int = MIN_PRODUCTION_SAMPLES,
) -> dict[str, Any]:
    input_files: dict[str, dict[str, Any]] = {}

    if model_status is None:
        loaded, status = read_json_object(model_status_path)
        model_status = loaded
        input_files["model_status"] = status
    if calibration_report is None:
        loaded, status = read_json_object(calibration_report_path)
        calibration_report = loaded
        input_files["calibration_report"] = status
    if sample_state is None:
        loaded, status = read_json_object(sample_state_path)
        sample_state = loaded
        input_files["sample_state"] = status
    if data_contract_report is None:
        loaded, status = read_json_object(data_contract_path)
        data_contract_report = loaded
        input_files["data_contract_report"] = status

    model_status = dict(model_status or {})
    calibration_report = dict(calibration_report or {})
    sample_state = dict(sample_state or {})
    data_contract_report = dict(data_contract_report or {})

    model_source = normalize_model_source(model_status.get("model_source"))
    feature_schema_hash = current_feature_schema_hash()
    artifact_hash = str(model_status.get("artifact_feature_schema_hash") or "")
    feature_schema_match = bool(model_status.get("feature_schema_match")) and artifact_hash == feature_schema_hash

    clean_train_samples = first_int(
        model_status.get("clean_train_samples"),
        sample_state.get("clean_train_samples"),
        sample_state.get("train_eligible_samples"),
        sample_state.get("clean_settled_snapshots"),
        default=0,
    )
    settled_predictions = first_int(
        calibration_report.get("sample_count"),
        sample_state.get("settled_predictions"),
        sample_state.get("settled_prediction_count"),
        default=0,
    )
    production_samples = first_int(
        model_status.get("production_samples"),
        sample_state.get("production_samples"),
        sample_state.get("production_prediction_count"),
        default=0,
    )

    blockers: list[str] = []
    warnings: list[str] = []
    blockers.extend(safety_blockers(model_status, calibration_report, sample_state, data_contract_report))

    if model_source not in MODEL_SOURCES:
        blockers.append("model_source_not_allowed")
    if model_source == "manual_baseline":
        blockers.append("manual_baseline_cannot_claim_production_model")
    if clean_train_samples < min_clean_train_samples:
        blockers.append("clean_train_samples_below_300")
    if settled_predictions < min_settled_predictions:
        blockers.append("settled_predictions_below_500")
    if production_samples < min_production_samples:
        blockers.append("production_samples_below_1000")
    if not feature_schema_match:
        blockers.append("feature_schema_hash_mismatch")

    calibration_status = str(calibration_report.get("status") or "missing")
    if calibration_status == "insufficient_sample":
        blockers.append("calibration_report_insufficient_sample")

    model_logloss = finite_or_none(calibration_report.get("model_logloss"))
    model_brier = finite_or_none(calibration_report.get("model_brier") or calibration_report.get("multiclass_brier_score"))

    data_contract_status = str(data_contract_report.get("status") or "missing")
    if data_contract_report and data_contract_status not in {"ok", "passed"}:
        blockers.append("data_contract_not_ok")
    elif not data_contract_report:
        warnings.append("data_contract_report_missing")

    formal_calibration_allowed = settled_predictions >= min_settled_predictions and not safety_blockers(calibration_report)
    active_model_allowed = bool(model_status.get("active_model_allowed")) and model_source == "trained_artifact"
    production_ready = (
        not blockers
        and active_model_allowed
        and formal_calibration_allowed
        and production_samples >= min_production_samples
        and feature_schema_match
    )

    if production_ready:
        status = "production_ready"
    elif clean_train_samples < min_clean_train_samples or settled_predictions < min_settled_predictions:
        status = "insufficient_samples"
    else:
        status = "blocked"

    report = {
        "report_type": "football_promotion_gate_report",
        "generated_at": utc_now(),
        "status": status,
        "input_files": input_files,
        "model_source": model_source,
        "allowed_model_sources": list(MODEL_SOURCES),
        "active_model_allowed": active_model_allowed,
        "formal_calibration_allowed": formal_calibration_allowed,
        "production_ready": production_ready,
        "clean_train_samples": clean_train_samples,
        "minimum_clean_train_samples": min_clean_train_samples,
        "settled_predictions": settled_predictions,
        "minimum_settled_predictions": min_settled_predictions,
        "production_samples": production_samples,
        "minimum_production_samples": min_production_samples,
        "feature_schema_hash": feature_schema_hash,
        "artifact_feature_schema_hash": artifact_hash,
        "feature_schema_match": feature_schema_match,
        "calibration_status": calibration_status,
        "diagnostic_metrics": {
            "model_brier": model_brier,
            "model_logloss": model_logloss,
        },
        "blockers": sorted(set(blockers)),
        "warnings": warnings,
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
            "production_deploy_allowed": False,
        },
        "notes": [
            "Promotion gate is audit-only and does not deploy models.",
            "Odds or market data remain market_consensus, external_signal, or paper_tracking only.",
        ],
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(json_safe(report), indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")
    return report
