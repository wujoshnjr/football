from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EXPECTED_WORLD_CUP_FIXTURE_COUNT = 104
MINIMUM_WORLD_CUP_FIXTURE_COUNT = 48
DEFAULT_FIXTURE_TIMEZONE = "Asia/Taipei"

COMPLETED_STATUSES = {"completed", "finished", "final", "full_time", "ft", "aet", "pen"}
LIVE_STATUSES = {"live", "in_progress", "in-play", "in_play", "1h", "2h", "ht", "et"}
SCHEDULED_STATUSES = {"scheduled", "timed", "not_started", "not started", "ns", "tbd", "pre", "preview"}
ALLOWED_STATUS_FILTERS = {"all", "completed", "scheduled", "live"}
SAFE_PROVENANCE_KEYS = {"source_key", "source_event_id", "checked_at", "raw_record_index", "role", "source_name"}


def safe_timezone(tz_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name or DEFAULT_FIXTURE_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_FIXTURE_TIMEZONE)


def current_date_for_timezone(tz_name: str | None = DEFAULT_FIXTURE_TIMEZONE) -> date:
    return datetime.now(safe_timezone(tz_name)).date()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc


def parse_datetime(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def kickoff_date(value: str | None, tz_name: str | None = DEFAULT_FIXTURE_TIMEZONE) -> date | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    parsed = parse_datetime(text)
    if parsed is None:
        return None
    return parsed.astimezone(safe_timezone(tz_name)).date()


def kickoff_in_taiwan(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value
    parsed = parse_datetime(value)
    if parsed is None:
        return value
    return parsed.astimezone(safe_timezone(DEFAULT_FIXTURE_TIMEZONE)).isoformat()


def normalize_status(value: Any) -> str:
    raw = str(value or "scheduled").strip().lower()
    if raw in COMPLETED_STATUSES:
        return "completed"
    if raw in LIVE_STATUSES:
        return "live"
    if raw in SCHEDULED_STATUSES:
        return "scheduled"
    return raw or "scheduled"


def team_name(record: dict[str, Any], flat_key: str, nested_key: str) -> str | None:
    flat = record.get(flat_key)
    if isinstance(flat, str) and flat.strip():
        return flat.strip()
    nested = record.get(nested_key)
    if isinstance(nested, str) and nested.strip():
        return nested.strip()
    if isinstance(nested, dict):
        for key in ("name", "country", "id"):
            value = nested.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def safe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def winner(home_team: str, away_team: str, home_score: int | None, away_score: int | None, status: str) -> str | None:
    if status != "completed" or home_score is None or away_score is None:
        return None
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return "draw"


def result_label(home_team: str, away_team: str, home_score: int | None, away_score: int | None, status: str) -> str | None:
    match_winner = winner(home_team, away_team, home_score, away_score, status)
    if match_winner is None:
        return None
    if match_winner == "draw":
        return "draw"
    return f"{match_winner} win"


def source_provenance(record: dict[str, Any], source_used: str, generated_at: str) -> list[dict[str, Any]]:
    raw_items = record.get("source_provenance")
    items: list[dict[str, Any]] = []
    if isinstance(raw_items, list):
        for item in raw_items:
            if isinstance(item, dict):
                sanitized = {key: item.get(key) for key in SAFE_PROVENANCE_KEYS if key in item}
                if sanitized:
                    items.append(sanitized)
    if items:
        return items

    source_keys = record.get("source_keys")
    if isinstance(source_keys, list):
        keys = [str(key) for key in source_keys if key]
    else:
        key = record.get("source_key") or source_used
        keys = [str(key)] if key else [source_used]

    return [
        {
            "source_key": key,
            "checked_at": generated_at,
            "role": "fixture_source",
        }
        for key in keys
    ]


def normalize_product_fixture(record: dict[str, Any], source_used: str, generated_at: str) -> dict[str, Any] | None:
    home = team_name(record, "home_team_name", "home_team")
    away = team_name(record, "away_team_name", "away_team")
    if not home or not away:
        return None

    status = normalize_status(record.get("status"))
    home_score = safe_int(record.get("home_score"))
    away_score = safe_int(record.get("away_score"))
    fixture_id = str(record.get("fixture_id") or record.get("id") or f"{home}-{away}-{record.get('kickoff_time') or 'unknown'}")
    last_updated_at = record.get("last_updated_at") or record.get("updated_at") or record.get("checked_at") or generated_at
    finalized_at = record.get("finalized_at") or (last_updated_at if status == "completed" else None)

    payload = {
        "id": fixture_id,
        "fixture_id": fixture_id,
        "home_team": home,
        "away_team": away,
        "kickoff_time": record.get("kickoff_time") or "unknown",
        "kickoff_time_taiwan": kickoff_in_taiwan(record.get("kickoff_time")),
        "venue": record.get("venue"),
        "stage": record.get("stage") or "unknown",
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "winner": winner(home, away, home_score, away_score, status),
        "result": result_label(home, away, home_score, away_score, status),
        "finalized_at": finalized_at,
        "source_provenance": source_provenance(record, source_used, generated_at),
        "source_keys": [item.get("source_key") for item in source_provenance(record, source_used, generated_at) if item.get("source_key")],
        "last_updated_at": last_updated_at,
    }
    return payload


def normalize_product_fixtures(records: Iterable[dict[str, Any]], source_used: str, generated_at: str) -> list[dict[str, Any]]:
    fixtures = [normalize_product_fixture(record, source_used, generated_at) for record in records if isinstance(record, dict)]
    return sorted(
        [fixture for fixture in fixtures if fixture is not None],
        key=lambda fixture: (fixture.get("kickoff_time") or "9999", fixture.get("home_team") or ""),
    )


def data_completeness_report(
    fixtures: list[dict[str, Any]],
    *,
    source_used: str,
    today: date,
    tz: str,
) -> dict[str, Any]:
    tomorrow = today + timedelta(days=1)
    completed_count = sum(1 for fixture in fixtures if fixture.get("status") == "completed")
    scheduled_count = sum(1 for fixture in fixtures if fixture.get("status") == "scheduled")
    tomorrow_count = sum(1 for fixture in fixtures if kickoff_date(fixture.get("kickoff_time"), tz) == tomorrow)
    fixture_count = len(fixtures)

    missing_reason = None
    if source_used in {"demo", "demo_fallback"}:
        missing_reason = "demo_fallback_in_use"
    elif fixture_count == 0:
        missing_reason = "fixture_cache_missing_or_empty"
    elif fixture_count < MINIMUM_WORLD_CUP_FIXTURE_COUNT:
        missing_reason = f"fixture_count_below_minimum_{MINIMUM_WORLD_CUP_FIXTURE_COUNT}"
    elif fixture_count < EXPECTED_WORLD_CUP_FIXTURE_COUNT:
        missing_reason = f"fixture_count_below_expected_{EXPECTED_WORLD_CUP_FIXTURE_COUNT}"

    is_complete = missing_reason is None and fixture_count >= EXPECTED_WORLD_CUP_FIXTURE_COUNT
    return {
        "fixture_count": fixture_count,
        "completed_count": completed_count,
        "tomorrow_count": tomorrow_count,
        "scheduled_count": scheduled_count,
        "is_complete_worldcup_schedule": is_complete,
        "missing_reason": missing_reason,
        "source_used": source_used,
        "expected_fixture_count": EXPECTED_WORLD_CUP_FIXTURE_COUNT,
        "minimum_fixture_count": MINIMUM_WORLD_CUP_FIXTURE_COUNT,
    }


def filter_product_fixtures(
    fixtures: list[dict[str, Any]],
    *,
    status: str = "all",
    date_filter: str | None = None,
    target_date: date | None = None,
    stage: str | None = None,
    tz: str = DEFAULT_FIXTURE_TIMEZONE,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    normalized_status = status.lower().strip() if status else "all"
    if normalized_status not in ALLOWED_STATUS_FILTERS:
        raise ValueError("status must be one of: completed, scheduled, live, all")

    selected_date = target_date
    if date_filter:
        selected_date = parse_date(date_filter)

    filtered = fixtures
    if normalized_status != "all":
        filtered = [fixture for fixture in filtered if fixture.get("status") == normalized_status]
    if selected_date is not None:
        filtered = [fixture for fixture in filtered if kickoff_date(fixture.get("kickoff_time"), tz) == selected_date]
    if stage:
        stage_key = stage.strip().lower()
        filtered = [fixture for fixture in filtered if str(fixture.get("stage") or "").strip().lower() == stage_key]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


def build_fixture_api_payload(
    records: Iterable[dict[str, Any]],
    *,
    source_used: str,
    generated_at: str,
    today: date,
    status: str = "all",
    date_filter: str | None = None,
    target_date: date | None = None,
    stage: str | None = None,
    tz: str = DEFAULT_FIXTURE_TIMEZONE,
    limit: int | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    fixtures = normalize_product_fixtures(records, source_used=source_used, generated_at=generated_at)
    filtered = filter_product_fixtures(
        fixtures,
        status=status,
        date_filter=date_filter,
        target_date=target_date,
        stage=stage,
        tz=tz,
        limit=limit,
    )
    completeness = data_completeness_report(fixtures, source_used=source_used, today=today, tz=tz)
    payload_warnings = list(warnings or [])
    if not completeness["is_complete_worldcup_schedule"]:
        payload_warnings.append("資料仍在同步，fixture cache 尚未達完整世界盃賽程門檻。")
    if completeness["missing_reason"] == "demo_fallback_in_use":
        payload_warnings.append("Demo fallback is active; this is not a complete official World Cup schedule.")

    return {
        "generated_at": generated_at,
        "timezone": tz,
        "source_used": source_used,
        "filters": {
            "status": status,
            "date": date_filter or (target_date.isoformat() if target_date else None),
            "stage": stage,
            "limit": limit,
        },
        "fixture_count": len(filtered),
        "fixtures": filtered,
        "data_completeness": completeness,
        "warnings": payload_warnings,
        "usage_note": (
            "Fixture endpoints are read-only. They never connect to betting APIs, submit picks, "
            "or emit betting recommendations or stake sizing."
        ),
    }
