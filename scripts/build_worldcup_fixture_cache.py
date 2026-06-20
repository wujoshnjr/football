from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.services.fixture_ingestion_service import FixtureIngestionService
from app.services.fixture_product_service import (
    DEFAULT_FIXTURE_TIMEZONE,
    data_completeness_report,
    current_date_for_timezone,
    normalize_product_fixtures,
)

CACHE_PATH = ROOT / "data" / "cache" / "fixtures_latest.json"
REPORT_PATH = ROOT / "report" / "worldcup_fixture_cache_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def existing_cache_summary(cache_path: Path) -> dict[str, Any]:
    if not cache_path.exists():
        return {"exists": False, "path": str(cache_path.relative_to(ROOT)), "fixture_count": 0, "generated_at": None}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "exists": True,
            "path": str(cache_path.relative_to(ROOT)),
            "fixture_count": 0,
            "generated_at": None,
            "error": f"cache_read_error: {exc}",
        }
    fixtures = payload.get("fixtures", []) if isinstance(payload, dict) else []
    return {
        "exists": True,
        "path": str(cache_path.relative_to(ROOT)),
        "fixture_count": len(fixtures) if isinstance(fixtures, list) else 0,
        "generated_at": payload.get("generated_at") if isinstance(payload, dict) else None,
    }


def failure_report(error: str, started_at: str, cache_path: Path, report_path: Path) -> dict[str, Any]:
    return {
        "ok": False,
        "generated_at": utc_now(),
        "started_at": started_at,
        "cache_path": str(cache_path.relative_to(ROOT)),
        "report_path": str(report_path.relative_to(ROOT)),
        "cache_written": False,
        "fixture_count": 0,
        "completed_count": 0,
        "tomorrow_count": 0,
        "scheduled_count": 0,
        "is_complete_worldcup_schedule": False,
        "missing_reason": error,
        "source_used": "fixture_ingestion_service",
        "previous_cache": existing_cache_summary(cache_path),
        "errors": [error],
        "warnings": [],
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
        },
        "usage_note": "Fixture cache build failed without crashing. Existing cache was preserved.",
    }


def build_worldcup_fixture_cache(
    *,
    timeout_seconds: int = 12,
    allow_empty: bool = False,
    cache_path: Path = CACHE_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    started_at = utc_now()
    settings = get_settings()
    service = FixtureIngestionService(settings, timeout_seconds=timeout_seconds)

    try:
        ingestion_report = service.ingest()
    except Exception as exc:  # noqa: BLE001 - script emits JSON report instead of crashing
        report = failure_report(f"ingestion_exception: {type(exc).__name__}", started_at, cache_path, report_path)
        write_json(report_path, report)
        return report

    if not isinstance(ingestion_report, dict):
        report = failure_report("schema_mismatch: ingestion report is not an object", started_at, cache_path, report_path)
        write_json(report_path, report)
        return report

    raw_fixtures = ingestion_report.get("fixtures", [])
    if not isinstance(raw_fixtures, list):
        report = failure_report("schema_mismatch: fixtures is not a list", started_at, cache_path, report_path)
        write_json(report_path, report)
        return report

    generated_at = ingestion_report.get("generated_at") or utc_now()
    fixtures = normalize_product_fixtures(
        [record for record in raw_fixtures if isinstance(record, dict)],
        source_used="fixture_ingestion_service",
        generated_at=generated_at,
    )
    completeness = data_completeness_report(
        fixtures,
        source_used="fixture_ingestion_service",
        today=current_date_for_timezone(DEFAULT_FIXTURE_TIMEZONE),
        tz=DEFAULT_FIXTURE_TIMEZONE,
    )
    cache_payload = {
        "generated_at": generated_at,
        "synced_at": utc_now(),
        "source_used": "fixture_ingestion_service",
        "fixture_count": len(fixtures),
        "data_completeness": completeness,
        "fixtures": fixtures,
        "source_reports": ingestion_report.get("source_reports", []),
        "sources": ingestion_report.get("sources", []),
        "usage_note": (
            "Generated by scripts/build_worldcup_fixture_cache.py. This cache is read-only schedule data; "
            "it does not connect to betting APIs, submit picks, output recommended bets, or output stake sizing."
        ),
    }

    should_write_cache = bool(fixtures) or allow_empty
    report = {
        "ok": should_write_cache,
        "generated_at": utc_now(),
        "started_at": started_at,
        "cache_path": str(cache_path.relative_to(ROOT)),
        "report_path": str(report_path.relative_to(ROOT)),
        "cache_written": should_write_cache,
        "allow_empty": allow_empty,
        "previous_cache": existing_cache_summary(cache_path),
        "source_used": "fixture_ingestion_service",
        "fixture_count": completeness["fixture_count"],
        "completed_count": completeness["completed_count"],
        "tomorrow_count": completeness["tomorrow_count"],
        "scheduled_count": completeness["scheduled_count"],
        "is_complete_worldcup_schedule": completeness["is_complete_worldcup_schedule"],
        "missing_reason": completeness["missing_reason"],
        "source_reports": ingestion_report.get("source_reports", []),
        "sources": ingestion_report.get("sources", []),
        "errors": ingestion_report.get("errors", []),
        "warnings": ingestion_report.get("warnings", []),
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
        },
        "usage_note": (
            "If fixture_count is below the full 2026 World Cup schedule, the cache remains explicitly incomplete. "
            "The frontend must show that state instead of presenting demo or partial data as complete."
        ),
    }

    if should_write_cache:
        write_json(cache_path, cache_payload)
    else:
        report["ok"] = False
        report["missing_reason"] = report["missing_reason"] or "empty_ingestion_result"
        report["warnings"].append("No fixtures returned; existing cache was preserved.")

    write_json(report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the 2026 World Cup fixture cache and completeness report.")
    parser.add_argument("--timeout-seconds", type=int, default=12, help="Timeout per provider request. Default: 12.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow writing an empty cache payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_worldcup_fixture_cache(timeout_seconds=args.timeout_seconds, allow_empty=args.allow_empty)
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
