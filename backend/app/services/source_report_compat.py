from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.schemas import DataSourceStatus

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.source_registry import CANONICAL_SOURCE_KEYS, get_source_status, list_sources  # noqa: E402
from scripts.source_report_schema import (  # noqa: E402
    SUPPORTED_SOURCE_STATUSES,
    build_source_report,
    validate_source_report,
)

CATEGORY_BY_PRODUCTION_USE = {
    "primary_fixture_source": "primary_api",
    "fixture_cross_check": "fixture_cross_check",
    "offline_fixture_seed": "open_data",
    "metadata_enrichment": "metadata_api",
    "offline_training_data": "offline_training",
    "weather_feature_source": "weather_api",
    "news_signal_source": "news_api",
    "team_strength_source": "team_strength_source",
    "external_prediction_benchmark_read_only": "external_prediction_benchmark",
}

RELIABILITY_BY_PRODUCTION_USE = {
    "primary_fixture_source": 0.88,
    "fixture_cross_check": 0.72,
    "offline_fixture_seed": 0.64,
    "metadata_enrichment": 0.54,
    "offline_training_data": 0.80,
    "weather_feature_source": 0.66,
    "news_signal_source": 0.50,
    "team_strength_source": 0.78,
    "external_prediction_benchmark_read_only": 0.62,
}

LEGACY_STATUS_MAP = {
    "adapter_exception": "upstream_error",
    "missing_url": "missing_credentials",
    "parse_error": "schema_mismatch",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_source_registry(environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    """Return the canonical 13-source registry without exposing secret values."""

    env = environ if environ is not None else os.environ
    return list_sources(env)


def canonical_data_source_statuses(environ: Mapping[str, str] | None = None) -> list[DataSourceStatus]:
    return [source_to_data_source_status(source) for source in canonical_source_registry(environ)]


def source_to_data_source_status(source: Mapping[str, Any]) -> DataSourceStatus:
    production_use = str(source.get("production_use") or "fixture_cross_check")
    warnings = source.get("warnings") if isinstance(source.get("warnings"), list) else []
    missing_reason = source.get("missing_reason")
    notes_parts = [production_use]
    if missing_reason:
        notes_parts.append(str(missing_reason))
    notes_parts.extend(str(warning) for warning in warnings)

    return DataSourceStatus(
        key=str(source["key"]),
        name=str(source.get("name") or source["key"]),
        category=CATEGORY_BY_PRODUCTION_USE.get(production_use, "source"),
        priority=int(source.get("priority") or 999),
        reliability=RELIABILITY_BY_PRODUCTION_USE.get(production_use, 0.50),
        requires_key=bool(source.get("requires_key", False)),
        configured=bool(source.get("configured", False)),
        enabled=bool(source.get("enabled", False)),
        role=str(source.get("role") or "Canonical football data source."),
        notes="; ".join(notes_parts),
    )


def normalize_ingestion_report_source_reports(
    payload: Mapping[str, Any],
    *,
    checked_at: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Normalize any legacy ingestion report into a report with valid source_reports."""

    normalized_payload = dict(payload)
    raw_reports = normalized_payload.get("source_reports") or normalized_payload.get("sources") or []
    normalized_payload["source_reports"] = normalize_source_reports(raw_reports, checked_at=checked_at, environ=environ)
    return normalized_payload


def normalize_source_reports(
    reports: Any,
    *,
    checked_at: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(reports, list):
        reports = []
    return [normalize_source_report(report, checked_at=checked_at, environ=environ) for report in reports]


def normalize_source_report(
    report: Any,
    *,
    checked_at: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if isinstance(report, Mapping):
        candidate = dict(report)
        try:
            validate_source_report(candidate)
            return candidate
        except ValueError:
            return legacy_source_report_to_source_report(candidate, checked_at=checked_at, environ=environ)

    return legacy_source_report_to_source_report(
        {"source_key": "unknown", "status": "schema_mismatch", "error": "source report is not an object"},
        checked_at=checked_at,
        environ=environ,
    )


def legacy_source_report_to_source_report(
    legacy: Mapping[str, Any],
    *,
    checked_at: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source_key = legacy_source_key(legacy)
    source = source_payload_for_report(source_key, legacy, environ=environ)
    missing_env = list(legacy.get("missing_env") or source.get("missing_env") or [])
    status = normalize_source_status(legacy, missing_env)
    success = bool(legacy.get("ok", legacy.get("success", False))) and status == "ok"
    error = legacy.get("error")
    if error is not None:
        error = str(error)

    report = build_source_report(
        source,
        attempted=bool(legacy.get("attempted", False)),
        success=success,
        status=status,
        record_count=non_negative_int(legacy.get("normalized_record_count", legacy.get("record_count", 0))),
        error=error,
        missing_env=missing_env,
        checked_at=str(legacy.get("generated_at") or checked_at or utc_now()),
    )
    validate_source_report(report)
    return report


def legacy_source_key(legacy: Mapping[str, Any]) -> str:
    source = legacy.get("source")
    if isinstance(source, Mapping) and source.get("key"):
        return str(source["key"])
    for key in ("source_key", "key"):
        if legacy.get(key):
            return str(legacy[key])
    return "unknown"


def source_payload_for_report(
    source_key: str,
    legacy: Mapping[str, Any],
    *,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    try:
        return get_source_status(source_key, environ if environ is not None else os.environ)
    except KeyError:
        return {
            "key": source_key,
            "name": str(legacy.get("source_name") or source_key),
            "requires_key": False,
            "official": False,
            "role": "Legacy backend source adapter.",
            "production_use": "legacy_adapter",
            "priority": 999,
            "env_vars": [],
            "enabled_env": None,
            "enabled": bool(legacy.get("enabled", False)),
            "configured": bool(legacy.get("configured", False)),
            "missing_env": [],
            "missing_reason": None,
            "world_cup_ids": {},
            "safety_flags": {},
            "warnings": [],
        }


def normalize_source_status(legacy: Mapping[str, Any], missing_env: list[str]) -> str:
    raw_status = str(legacy.get("status") or "").strip()
    mapped_status = LEGACY_STATUS_MAP.get(raw_status, raw_status)
    if mapped_status in SUPPORTED_SOURCE_STATUSES:
        return mapped_status
    if bool(legacy.get("ok", legacy.get("success", False))):
        return "ok"
    if bool(missing_env):
        return "missing_credentials"
    if legacy.get("enabled") is False:
        return "disabled"
    return "upstream_error"


def non_negative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)
