from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TRACKED_ARTIFACTS: tuple[str, ...] = (
    "report/prediction.json",
    "report/fixture_ingestion_report.json",
    "report/source_health_report.json",
    "report/baseline_comparison_report.json",
    "report/calibration_report.json",
    "report/promotion_gate_report.json",
    "report/data_contract_report.json",
    "report/pipeline_manifest.json",
    "data/fixtures.csv",
    "data/finalized_fixtures.csv",
    "data/prediction_snapshots.csv",
    "data/market_odds_history.csv",
    "data/team_strength_context.csv",
    "data/weather_context.csv",
    "data/injury_context.csv",
    "data/lineup_context.csv",
    "data/sample_state.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_row_count(path: Path) -> int | None:
    try:
        with path.open("r", newline="", encoding="utf-8") as file_obj:
            reader = csv.reader(file_obj)
            rows = list(reader)
    except (OSError, UnicodeDecodeError):
        return None
    if not rows:
        return 0
    return max(len(rows) - 1, 0)


def json_top_level(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - manifest records parse errors instead of crashing
        return {"json_valid": False, "json_error": str(exc), "json_type": None, "json_top_level_keys": []}
    if isinstance(payload, dict):
        return {"json_valid": True, "json_error": None, "json_type": "dict", "json_top_level_keys": sorted(payload.keys())}
    if isinstance(payload, list):
        return {"json_valid": True, "json_error": None, "json_type": "list", "json_top_level_keys": []}
    return {"json_valid": True, "json_error": None, "json_type": type(payload).__name__, "json_top_level_keys": []}


def artifact_summary(root: Path, relative_path: str) -> dict[str, Any]:
    path = root / relative_path
    exists = path.exists() and path.is_file()
    summary: dict[str, Any] = {
        "path": relative_path,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else 0,
        "sha256": sha256_file(path) if exists else None,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat() if exists else None,
        "csv_row_count": None,
        "json_valid": None,
        "json_error": None,
        "json_type": None,
        "json_top_level_keys": [],
    }
    if not exists:
        return summary
    if path.suffix.lower() == ".csv":
        summary["csv_row_count"] = csv_row_count(path)
    if path.suffix.lower() == ".json":
        summary.update(json_top_level(path))
    return summary


def build_pipeline_manifest(
    root: Path = Path("."),
    artifacts: Iterable[str] = TRACKED_ARTIFACTS,
) -> dict[str, Any]:
    artifact_list = list(artifacts)
    summaries = [artifact_summary(root, relative_path) for relative_path in artifact_list]
    existing_count = sum(1 for item in summaries if item["exists"])
    missing_count = len(summaries) - existing_count
    return {
        "report_type": "football_pipeline_manifest",
        "generated_at": utc_now(),
        "artifact_count": len(summaries),
        "existing_count": existing_count,
        "missing_count": missing_count,
        "artifacts": summaries,
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
        },
    }


def write_pipeline_manifest(root: Path = Path("."), output_path: str = "report/pipeline_manifest.json") -> dict[str, Any]:
    manifest = build_pipeline_manifest(root=root)
    path = root / output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
    return manifest
