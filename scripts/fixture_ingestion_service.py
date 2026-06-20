from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scripts.source_registry import get_source_status
from scripts.source_report_schema import build_source_report


PHASE_ONE_FIXTURE_SOURCE_KEYS: tuple[str, ...] = (
    "football_data",
    "api_football",
    "worldcup_2026_api",
    "openfootball_worldcup_json",
    "sportsdataio_worldcup",
    "thestatsapi_worldcup",
)

Adapter = Callable[[], Any]


class FixtureIngestionService:
    """Build a no-crash fixture ingestion report from injected read-only adapters.

    This script-level service is intentionally network-agnostic. Callers provide adapters,
    and tests provide fakes. Missing env, missing adapters, adapter exceptions, empty
    responses, and schema mismatches are recorded in JSON reports instead of raising.
    """

    def __init__(
        self,
        adapters: Mapping[str, Adapter | Any] | None = None,
        environ: Mapping[str, str] | None = None,
        fixture_source_keys: tuple[str, ...] = PHASE_ONE_FIXTURE_SOURCE_KEYS,
    ) -> None:
        self.adapters = dict(adapters or {})
        self.environ = environ
        self.fixture_source_keys = fixture_source_keys

    def run(self) -> dict[str, Any]:
        checked_at = utc_now()
        source_reports: list[dict[str, Any]] = []
        fixture_candidates: list[dict[str, Any]] = []
        errors: list[str] = []
        warnings: list[str] = []

        for source_key in self.fixture_source_keys:
            source = get_source_status(source_key, self.environ)
            adapter = self.adapters.get(source_key)

            if not source["enabled"] or not source["configured"]:
                report = build_source_report(
                    source,
                    attempted=False,
                    success=False,
                    error=source.get("missing_reason"),
                    checked_at=checked_at,
                )
                report["raw_record_count"] = 0
                report["normalized_record_count"] = 0
                source_reports.append(report)
                continue

            if adapter is None:
                warnings.append(f"{source_key}: adapter_not_configured")
                report = build_source_report(
                    source,
                    attempted=False,
                    success=False,
                    status="disabled",
                    record_count=0,
                    error="adapter_not_configured",
                    checked_at=checked_at,
                )
                report["raw_record_count"] = 0
                report["normalized_record_count"] = 0
                source_reports.append(report)
                continue

            try:
                payload = adapter() if callable(adapter) else adapter
                raw_records = extract_adapter_records(payload)
                normalized = normalize_fixture_records(source_key, raw_records, checked_at)
            except Exception as exc:  # noqa: BLE001 - ingestion must report failures, not crash
                status = classify_exception(exc)
                errors.append(f"{source_key}: {status}: {exc}")
                report = build_source_report(
                    source,
                    attempted=True,
                    success=False,
                    status=status,
                    record_count=0,
                    error=str(exc),
                    checked_at=checked_at,
                )
                report["raw_record_count"] = 0
                report["normalized_record_count"] = 0
                source_reports.append(report)
                continue

            if not raw_records:
                report = build_source_report(
                    source,
                    attempted=True,
                    success=False,
                    status="empty_response",
                    record_count=0,
                    error="empty_response",
                    checked_at=checked_at,
                )
            elif not normalized:
                errors.append(f"{source_key}: schema_mismatch: no_normalized_fixture_records")
                report = build_source_report(
                    source,
                    attempted=True,
                    success=False,
                    status="schema_mismatch",
                    record_count=len(raw_records),
                    error="no_normalized_fixture_records",
                    checked_at=checked_at,
                )
            else:
                fixture_candidates.extend(normalized)
                report = build_source_report(
                    source,
                    attempted=True,
                    success=True,
                    status="ok",
                    record_count=len(raw_records),
                    checked_at=checked_at,
                )

            report["raw_record_count"] = len(raw_records)
            report["normalized_record_count"] = len(normalized)
            source_reports.append(report)

        fixtures = merge_fixture_candidates(fixture_candidates)
        return build_ingestion_report(
            checked_at=checked_at,
            source_reports=source_reports,
            fixtures=fixtures,
            errors=errors,
            warnings=warnings,
        )

    def write_report(self, path: str | Path = "report/fixture_ingestion_report.json") -> dict[str, Any]:
        report = self.run()
        report_path = Path(path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False), encoding="utf-8")
        return report


def build_ingestion_report(
    *,
    checked_at: str,
    source_reports: list[dict[str, Any]],
    fixtures: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    teams = {
        team
        for fixture in fixtures
        for team in (fixture.get("home_team_name"), fixture.get("away_team_name"))
        if team
    }
    groups = {fixture.get("stage") for fixture in fixtures if fixture.get("stage")}
    return {
        "run_id": uuid.uuid4().hex,
        "checked_at": checked_at,
        "fixture_count": len(fixtures),
        "merged_fixture_count": len(fixtures),
        "teams_count": len(teams),
        "groups_count": len(groups),
        "source_reports": source_reports,
        "fixtures": fixtures,
        "errors": errors,
        "warnings": warnings,
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
            "pick_submission_allowed": False,
        },
        "usage_note": "Fixture ingestion is read-only and produces audit reports for engineering validation.",
    }


def extract_adapter_records(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        raise ValueError("adapter payload must be a dict or list")

    if "records" in payload and isinstance(payload["records"], list):
        return [item for item in payload["records"] if isinstance(item, dict)]

    for key in ("fixtures", "matches", "events", "games", "Games", "response", "data", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def normalize_fixture_records(source_key: str, records: list[dict[str, Any]], checked_at: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        fixture = normalize_fixture_record(source_key, record, checked_at, index)
        if fixture:
            normalized.append(fixture)
    return normalized


def normalize_fixture_record(source_key: str, record: Mapping[str, Any], checked_at: str, raw_record_index: int) -> dict[str, Any] | None:
    home = first_text(record, ["home_team_name", "home_team", "homeTeam", "home", "team1", "HomeTeamName", "HomeTeam"])
    away = first_text(record, ["away_team_name", "away_team", "awayTeam", "away", "team2", "AwayTeamName", "AwayTeam"])
    if not valid_team_pair(home, away):
        return None

    kickoff = first_text(
        record,
        ["kickoff_time", "kickoff", "utcDate", "date", "datetime", "DateTime", "match_date", "start_time", "Day"],
    )
    stage = first_text(record, ["stage", "round", "group", "Group", "Round", "name"]) or "world_cup"
    venue = first_text(record, ["venue", "stadium", "ground", "location", "Venue", "Stadium"])
    status = normalize_status(first_text(record, ["status", "state", "Status"]))
    source_event_id = first_text(record, ["source_event_id", "id", "event_id", "match_id", "matchId", "GameId", "key"])
    home_score = first_int(record, ["home_score", "homeScore", "home_goals", "HomeTeamScore", "score1"])
    away_score = first_int(record, ["away_score", "awayScore", "away_goals", "AwayTeamScore", "score2"])
    fixture_id = stable_id("|".join([normalize_name(home), normalize_name(away), kickoff or "unknown"]))

    return {
        "id": fixture_id,
        "home_team_name": home,
        "away_team_name": away,
        "kickoff_time": kickoff,
        "venue": venue,
        "stage": stage,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "match_key": f"{normalize_name(home)}__{normalize_name(away)}",
        "source_keys": [source_key],
        "source_provenance": [
            {
                "source_key": source_key,
                "source_event_id": source_event_id,
                "checked_at": checked_at,
                "raw_record_index": raw_record_index,
                "role": "fixture_candidate",
            }
        ],
    }


def merge_fixture_candidates(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str | None], dict[str, Any]] = {}
    for record in records:
        key = (str(record.get("match_key") or ""), record.get("kickoff_time"))
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(record)
            continue

        existing_sources = list(existing.get("source_keys", []))
        for source_key in record.get("source_keys", []):
            if source_key not in existing_sources:
                existing_sources.append(source_key)
        existing["source_keys"] = existing_sources
        existing["source_provenance"] = list(existing.get("source_provenance", [])) + list(record.get("source_provenance", []))
        for field in ("venue", "stage", "status", "home_score", "away_score"):
            if existing.get(field) in (None, "", "unknown", "scheduled") and record.get(field) not in (None, ""):
                existing[field] = record[field]

    return sorted(merged.values(), key=lambda item: (str(item.get("kickoff_time") or "9999"), item.get("home_team_name") or ""))


def classify_exception(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "timeout"
    return "upstream_error"


def first_text(item: Mapping[str, Any], keys: list[str]) -> str | None:
    for key in keys:
        if key in item:
            text = extract_text(item[key])
            if text:
                return text
    return None


def extract_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Mapping):
        return first_text(value, ["displayName", "name", "shortName", "country", "code", "Name", "TeamName"])
    return None


def first_int(item: Mapping[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        if key in item:
            value = safe_int(item[key])
            if value is not None:
                return value
    return None


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def valid_team_pair(home: str | None, away: str | None) -> bool:
    return bool(home and away and normalize_name(home) != normalize_name(away))


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def normalize_status(status: str | None) -> str:
    raw = (status or "scheduled").strip().lower()
    if raw in {"ns", "tbd", "pre", "preview", "timed", "not started"}:
        return "scheduled"
    if raw in {"ft", "aet", "pen", "final", "finished", "match finished", "full time"}:
        return "finished"
    if raw in {"1h", "2h", "ht", "et", "bt", "live", "in progress", "in_play"}:
        return "in_progress"
    if raw in {"pst", "postponed"}:
        return "postponed"
    if raw in {"canc", "cancelled", "canceled"}:
        return "cancelled"
    return raw or "scheduled"


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
