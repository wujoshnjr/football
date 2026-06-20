from __future__ import annotations

import csv
import json
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from scripts.source_report_schema import validate_source_report


FORBIDDEN_OUTPUT_KEYS = {"recommended_bet", "stake_size"}
LOCKED_FALSE_FLAGS = {"live_betting_allowed", "automated_wagering_allowed", "real_money_betting_allowed"}
DEFAULT_REQUIRED_REPORTS = (
    "report/fixture_ingestion_report.json",
    "report/source_health_report.json",
)
DEFAULT_TRACKED_TEXT_PATHS = (
    ".env",
    ".env.example",
    "backend/app/config.py",
    "PROJECT_CONTEXT.md",
    "AGENTS.md",
)
SECRET_ASSIGNMENT_RE = re.compile(r"(?i)\b([A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD)[A-Z0-9_]*)\s*=\s*([^\s#]+)")
SECRET_LITERAL_RE = re.compile(r"(?i)\b(?:sk-[A-Za-z0-9_-]{16,}|tnm_[A-Za-z0-9_-]{12,})\b")
PLACEHOLDER_VALUES = {"", "changeme", "change_me", "placeholder", "example", "none", "null", "redacted", "your_key_here"}


@dataclass(frozen=True)
class ContractIssue:
    severity: str
    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def issue(severity: str, path: str, code: str, message: str) -> ContractIssue:
    return ContractIssue(severity=severity, path=path, code=code, message=message)


def validate_data_contract(
    root: Path = Path("."),
    required_reports: Iterable[str] = DEFAULT_REQUIRED_REPORTS,
    tracked_text_paths: Iterable[str] = DEFAULT_TRACKED_TEXT_PATHS,
    snapshot_path: str = "data/prediction_snapshots.csv",
) -> dict[str, Any]:
    issues: list[ContractIssue] = []
    checked_reports: list[str] = []

    for relative_path in required_reports:
        path = root / relative_path
        checked_reports.append(relative_path)
        payload = load_json_report(path, issues)
        if payload is None:
            continue
        validate_json_payload(payload, relative_path, issues)
        validate_required_report_fields(payload, relative_path, issues)
        validate_source_reports(payload, relative_path, issues)

    validate_snapshot_csv(root / snapshot_path, snapshot_path, issues)
    scan_tracked_files_for_api_keys(root, tracked_text_paths, issues)

    error_count = sum(1 for item in issues if item.severity == "error")
    warning_count = sum(1 for item in issues if item.severity == "warning")
    return {
        "report_type": "football_data_contract",
        "checked_at": utc_now(),
        "ok": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "checked_reports": checked_reports,
        "issues": [item.to_dict() for item in issues],
    }


def load_json_report(path: Path, issues: list[ContractIssue]) -> Any | None:
    if not path.exists():
        issues.append(issue("error", str(path), "missing_required_report", "Required report JSON is missing."))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(issue("error", str(path), "invalid_json", str(exc)))
        return None
    except OSError as exc:
        issues.append(issue("error", str(path), "read_error", str(exc)))
        return None


def validate_json_payload(payload: Any, path: str, issues: list[ContractIssue]) -> None:
    for bad_path in find_non_finite_json_values(payload):
        issues.append(issue("error", path, "non_finite_json", f"JSON contains NaN or Infinity at {bad_path}."))
    for bad_path in find_forbidden_keys(payload):
        issues.append(issue("error", path, "forbidden_betting_key", f"Forbidden betting output key at {bad_path}."))
    for flag_path, value in find_locked_flag_violations(payload):
        issues.append(issue("error", path, "safety_flag_true", f"{flag_path} must be false, got {value!r}."))


def validate_required_report_fields(payload: Any, path: str, issues: list[ContractIssue]) -> None:
    if not isinstance(payload, Mapping):
        issues.append(issue("error", path, "report_not_object", "Report JSON must be an object."))
        return

    if path.endswith("fixture_ingestion_report.json"):
        required = {"run_id", "checked_at", "fixture_count", "source_reports", "fixtures", "errors", "warnings", "safety"}
    elif path.endswith("source_health_report.json"):
        required = {"checked_at", "source_reports"}
    else:
        required = set()

    for key in sorted(required):
        if key not in payload:
            issues.append(issue("error", path, "missing_required_field", f"Missing required field: {key}"))


def validate_source_reports(payload: Any, path: str, issues: list[ContractIssue]) -> None:
    if not isinstance(payload, Mapping):
        return
    source_reports = payload.get("source_reports")
    if source_reports is None:
        return
    if not isinstance(source_reports, list):
        issues.append(issue("error", path, "source_reports_not_list", "source_reports must be a list."))
        return
    for index, report in enumerate(source_reports):
        if not isinstance(report, Mapping):
            issues.append(issue("error", path, "source_report_not_object", f"source_reports[{index}] must be an object."))
            continue
        try:
            validate_source_report(report)
        except ValueError as exc:
            issues.append(issue("error", path, "invalid_source_report", f"source_reports[{index}]: {exc}"))


def validate_snapshot_csv(path: Path, display_path: str, issues: list[ContractIssue]) -> None:
    if not path.exists():
        return
    try:
        with path.open("r", newline="", encoding="utf-8") as file_obj:
            reader = csv.DictReader(file_obj)
            headers = reader.fieldnames or []
            for key in headers:
                if key in FORBIDDEN_OUTPUT_KEYS:
                    issues.append(issue("error", display_path, "forbidden_snapshot_column", f"Forbidden snapshot column: {key}"))
            for row_index, row in enumerate(reader, start=1):
                for key, value in row.items():
                    if key in LOCKED_FALSE_FLAGS and str(value).strip().lower() == "true":
                        issues.append(issue("error", display_path, "snapshot_safety_flag_true", f"row {row_index}: {key} must be false"))
                    if str(value).strip().lower() in {"nan", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
                        issues.append(issue("error", display_path, "snapshot_non_finite", f"row {row_index}: {key} contains {value}"))
    except OSError as exc:
        issues.append(issue("error", display_path, "snapshot_read_error", str(exc)))


def scan_tracked_files_for_api_keys(root: Path, tracked_text_paths: Iterable[str], issues: list[ContractIssue]) -> None:
    for relative_path in tracked_text_paths:
        path = root / relative_path
        if not path.exists() or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            issues.append(issue("warning", relative_path, "tracked_file_read_error", str(exc)))
            continue

        for line_number, line in enumerate(text.splitlines(), start=1):
            for match in SECRET_ASSIGNMENT_RE.finditer(line):
                value = match.group(2).strip().strip('"\'')
                if value.lower() not in PLACEHOLDER_VALUES:
                    issues.append(issue("error", relative_path, "api_key_in_repo", f"possible secret assignment on line {line_number}"))
            if SECRET_LITERAL_RE.search(line):
                issues.append(issue("error", relative_path, "secret_literal_in_repo", f"possible secret literal on line {line_number}"))


def find_non_finite_json_values(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, float) and not math.isfinite(value):
        hits.append(path)
    elif isinstance(value, Mapping):
        for key, child in value.items():
            hits.extend(find_non_finite_json_values(child, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_non_finite_json_values(child, f"{path}[{index}]"))
    return hits


def find_forbidden_keys(value: Any, path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in FORBIDDEN_OUTPUT_KEYS:
                hits.append(child_path)
            hits.extend(find_forbidden_keys(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_forbidden_keys(child, f"{path}[{index}]"))
    return hits


def find_locked_flag_violations(value: Any, path: str = "$") -> list[tuple[str, Any]]:
    hits: list[tuple[str, Any]] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if key in LOCKED_FALSE_FLAGS and child is not False:
                hits.append((child_path, child))
            hits.extend(find_locked_flag_violations(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(find_locked_flag_violations(child, f"{path}[{index}]"))
    return hits


def write_data_contract_report(root: Path = Path("."), output_path: str = "report/data_contract_report.json") -> dict[str, Any]:
    report = validate_data_contract(root=root)
    path = root / output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
    return report
