from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping


SUPPORTED_SOURCE_STATUSES: tuple[str, ...] = (
    "ok",
    "disabled",
    "missing_credentials",
    "missing_world_cup_ids",
    "missing_world_cup_competition_key",
    "unauthorized_or_forbidden",
    "rate_limited",
    "upstream_error",
    "empty_response",
    "schema_mismatch",
    "timeout",
)

REQUIRED_SOURCE_REPORT_FIELDS: tuple[str, ...] = (
    "source",
    "attempted",
    "success",
    "status",
    "record_count",
    "error",
    "missing_env",
    "checked_at",
)


@dataclass(frozen=True)
class SourceReport:
    source: Mapping[str, Any]
    attempted: bool
    success: bool
    status: str
    record_count: int
    error: str | None
    missing_env: tuple[str, ...]
    checked_at: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source"] = dict(self.source)
        payload["missing_env"] = list(self.missing_env)
        return payload


def build_source_report(
    source: Mapping[str, Any],
    *,
    attempted: bool = False,
    success: bool | None = None,
    status: str | None = None,
    record_count: int = 0,
    error: str | None = None,
    missing_env: list[str] | tuple[str, ...] | None = None,
    checked_at: str | None = None,
) -> dict[str, Any]:
    source_payload = dict(source)
    inferred_missing = tuple(missing_env if missing_env is not None else source_payload.get("missing_env", ()))
    inferred_status = status or infer_status_from_source(source_payload, inferred_missing)
    inferred_success = bool(inferred_status == "ok") if success is None else bool(success)

    report = SourceReport(
        source=source_payload,
        attempted=bool(attempted),
        success=inferred_success,
        status=inferred_status,
        record_count=int(record_count),
        error=error,
        missing_env=tuple(str(item) for item in inferred_missing),
        checked_at=checked_at or utc_now(),
    ).to_dict()
    validate_source_report(report)
    return report


def infer_status_from_source(source: Mapping[str, Any], missing_env: tuple[str, ...]) -> str:
    if not source.get("enabled", False):
        return "disabled"
    if missing_env:
        return "missing_credentials" if source.get("requires_key", False) else "schema_mismatch"
    return "ok"


def validate_source_report(report: Mapping[str, Any]) -> None:
    missing_fields = [field for field in REQUIRED_SOURCE_REPORT_FIELDS if field not in report]
    if missing_fields:
        raise ValueError(f"source report missing required fields: {', '.join(missing_fields)}")

    source = report["source"]
    if not isinstance(source, Mapping) or not source.get("key"):
        raise ValueError("source report field 'source' must include a source key")

    status = report["status"]
    if status not in SUPPORTED_SOURCE_STATUSES:
        raise ValueError(f"unsupported source status: {status}")

    if not isinstance(report["attempted"], bool):
        raise ValueError("source report field 'attempted' must be a bool")
    if not isinstance(report["success"], bool):
        raise ValueError("source report field 'success' must be a bool")

    record_count = report["record_count"]
    if isinstance(record_count, bool) or not isinstance(record_count, int) or record_count < 0:
        raise ValueError("source report field 'record_count' must be a non-negative integer")

    error = report["error"]
    if error is not None and not isinstance(error, str):
        raise ValueError("source report field 'error' must be null or a string")

    missing_env = report["missing_env"]
    if not isinstance(missing_env, list) or any(not isinstance(item, str) for item in missing_env):
        raise ValueError("source report field 'missing_env' must be a list of strings")

    checked_at = report["checked_at"]
    if not isinstance(checked_at, str) or not checked_at:
        raise ValueError("source report field 'checked_at' must be a non-empty string")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
