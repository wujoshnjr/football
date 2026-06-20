import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.safety_policy import enforce_no_forbidden_output_keys
from app.schemas import DataSourceStatus, Fixture, ManualPredictionInput, ModelPerformance, TeamSnapshot
from app.services.advanced_feature_registry import advanced_feature_registry
from app.services.feature_table_service import build_match_feature_table
from app.services.fixture_ingestion_service import FixtureIngestionService, normalize_name
from app.services.fixture_product_service import (
    DEFAULT_FIXTURE_TIMEZONE,
    build_fixture_api_payload,
    current_date_for_timezone,
)
from app.services.prediction_service import PredictionService
from app.services.source_fusion_service import SourceFusionService
from app.services.source_report_compat import (
    canonical_data_source_statuses,
    canonical_source_registry,
    normalize_ingestion_report_source_reports,
)
from app.services.tournamental_odds_client import TournamentalOddsClient
from app.services.tournamental_odds_normalizer import find_market_signal_for_fixture, normalize_tournamental_snapshot
from app.services.tournamental_wc2026_client import TournamentalWC2026Client

settings = get_settings()
app = FastAPI(title=settings.app_name, version=settings.model_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT_DIR = Path(__file__).resolve().parents[2]
FIXTURE_CACHE_PATHS = [
    ROOT_DIR / "data" / "cache" / "fixtures_latest.json",
    ROOT_DIR / "data" / "raw" / "fixtures_latest.json",
    ROOT_DIR / "report" / "fixtures_latest.json",
]
SOURCE_HEALTH_REPORT_PATH = ROOT_DIR / "report" / "source_health_report.json"
WORLD_CUP_FIXTURE_CACHE_REPORT_PATH = ROOT_DIR / "report" / "worldcup_fixture_cache_report.json"
FIXTURE_SOURCE_DESCRIPTION = "Fixture source: auto, demo, cache, or ingestion."


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def api_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def locked_safety_flags() -> dict[str, bool]:
    return {
        "live_betting_allowed": False,
        "automated_wagering_allowed": False,
        "real_money_betting_allowed": False,
        "pick_submission_allowed": False,
    }


def to_plain_payload(payload: Any) -> Any:
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if isinstance(payload, list):
        return [to_plain_payload(item) for item in payload]
    if isinstance(payload, tuple):
        return [to_plain_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: to_plain_payload(value) for key, value in payload.items()}
    return payload


def safe_payload(payload: Any) -> Any:
    enforce_no_forbidden_output_keys(to_plain_payload(payload))
    return payload


def safe_fixture_ingestion_report() -> dict[str, Any]:
    checked_at = utc_now()
    try:
        payload = fixture_ingestion()
    except Exception as exc:  # noqa: BLE001 - API returns a JSON report instead of crashing
        payload = {
            "generated_at": checked_at,
            "checked_at": checked_at,
            "fixture_count": 0,
            "merged_fixture_count": 0,
            "teams_count": 0,
            "groups_count": 0,
            "sources": [],
            "source_reports": [],
            "fixtures": [],
            "errors": [
                api_error(
                    "fixture_ingestion_failed",
                    "Fixture ingestion failed before a report could be completed.",
                    {"error_type": type(exc).__name__},
                )
            ],
            "warnings": [],
            "safety": locked_safety_flags(),
            "usage_note": "Fixture ingestion is read-only and returns report JSON even when providers fail.",
        }

    if not isinstance(payload, dict):
        payload = {
            "generated_at": checked_at,
            "checked_at": checked_at,
            "fixture_count": 0,
            "merged_fixture_count": 0,
            "teams_count": 0,
            "groups_count": 0,
            "sources": [],
            "source_reports": [],
            "fixtures": [],
            "errors": [api_error("fixture_ingestion_invalid_report", "Fixture ingestion returned a non-object report.")],
            "warnings": [],
            "safety": locked_safety_flags(),
        }

    payload.setdefault("checked_at", payload.get("generated_at") or checked_at)
    payload = normalize_ingestion_report_source_reports(
        payload,
        checked_at=payload.get("checked_at") or payload.get("generated_at") or checked_at,
    )
    payload.setdefault("errors", [])
    payload.setdefault("warnings", [])
    payload.setdefault("safety", locked_safety_flags())
    payload.setdefault("usage_note", "Fixture ingestion is read-only and returns report JSON.")
    return safe_payload(payload)


def team(
    team_id: str,
    name: str,
    country: str,
    fifa_rank: int | None,
    elo_rating: float,
    recent_points_per_match: float,
    goals_for_per_match: float,
    goals_against_per_match: float,
) -> TeamSnapshot:
    return TeamSnapshot(
        id=team_id,
        name=name,
        country=country,
        fifa_rank=fifa_rank,
        elo_rating=elo_rating,
        recent_points_per_match=recent_points_per_match,
        goals_for_per_match=goals_for_per_match,
        goals_against_per_match=goals_against_per_match,
    )


def neutral_team(name: str) -> TeamSnapshot:
    team_id = normalize_name(name)[:12] or "team"
    return team(
        team_id=team_id,
        name=name,
        country=name,
        fifa_rank=None,
        elo_rating=1500,
        recent_points_per_match=1.4,
        goals_for_per_match=1.2,
        goals_against_per_match=1.2,
    )


def demo_fixtures() -> list[Fixture]:
    """Temporary verified fixtures until full live ingestion is enabled.

    Finished matches show scores instead of being treated as upcoming predictions.
    Upcoming matches keep date-only kickoff values when exact kickoff time is not yet
    synced from the live provider.
    """

    argentina = team("arg", "Argentina", "Argentina", 2, 2140, 2.2, 1.9, 0.7)
    algeria = team("alg", "Algeria", "Algeria", 35, 1760, 1.6, 1.4, 1.1)
    japan = team("jpn", "Japan", "Japan", 18, 1845, 2.0, 1.8, 0.9)
    netherlands = team("ned", "Netherlands", "Netherlands", 7, 1995, 1.9, 1.7, 0.8)
    austria = team("aut", "Austria", "Austria", 24, 1840, 1.8, 1.6, 1.0)
    jordan = team("jor", "Jordan", "Jordan", 66, 1585, 1.4, 1.2, 1.4)
    sweden = team("swe", "Sweden", "Sweden", 43, 1780, 1.6, 1.5, 1.1)
    tunisia = team("tun", "Tunisia", "Tunisia", 40, 1730, 1.5, 1.1, 1.0)

    return [
        Fixture(
            id="arg-alg-2026-final",
            home_team=argentina,
            away_team=algeria,
            kickoff_time="2026-06-17T01:00:00Z",
            venue="Kansas City Stadium",
            stage="Group J",
            status="finished",
            home_score=3,
            away_score=0,
        ),
        Fixture(
            id="ned-jpn-2026-final",
            home_team=netherlands,
            away_team=japan,
            kickoff_time="2026-06-14T20:00:00Z",
            venue="Dallas Stadium",
            stage="Group F",
            status="finished",
            home_score=2,
            away_score=2,
        ),
        Fixture(
            id="ned-swe-2026",
            home_team=netherlands,
            away_team=sweden,
            kickoff_time="2026-06-20",
            venue="Houston Stadium",
            stage="Group F",
            status="scheduled",
        ),
        Fixture(
            id="tun-jpn-2026",
            home_team=tunisia,
            away_team=japan,
            kickoff_time="2026-06-20",
            venue="Estadio Monterrey",
            stage="Group F",
            status="scheduled",
        ),
        Fixture(
            id="arg-aut-2026",
            home_team=argentina,
            away_team=austria,
            kickoff_time="2026-06-22",
            venue="Dallas Stadium",
            stage="Group J",
            status="scheduled",
        ),
        Fixture(
            id="jor-alg-2026",
            home_team=jordan,
            away_team=algeria,
            kickoff_time="2026-06-22",
            venue="San Francisco Bay Area Stadium",
            stage="Group J",
            status="scheduled",
        ),
    ]


def source_context():
    return SourceFusionService(settings).build_source_context()


def fixture_ingestion():
    return FixtureIngestionService(settings).ingest()


def load_json_file(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def source_health_report() -> dict[str, Any]:
    """Read the latest source-health artifact without calling external APIs.

    This keeps user-facing requests fast and avoids burning API quota on every page
    load. CI/Render jobs should refresh report/source_health_report.json by running
    scripts/build_source_health_report.py.
    """

    payload = load_json_file(SOURCE_HEALTH_REPORT_PATH)
    if isinstance(payload, dict):
        payload.setdefault("serving_mode", "cached_report")
        payload.setdefault("report_path", str(SOURCE_HEALTH_REPORT_PATH.relative_to(ROOT_DIR)))
        return payload

    context = source_context()
    configured = list(getattr(context, "sources_configured", []) or [])
    missing = list(getattr(context, "sources_missing", []) or [])
    return {
        "report_type": "source_health",
        "serving_mode": "report_missing",
        "generated_at": None,
        "source_count": len(configured) + len(missing),
        "ok_count": 0,
        "sources": [
            {
                "source_key": key,
                "attempted": False,
                "configured": True,
                "enabled": True,
                "ok": False,
                "status": "health_report_missing",
                "status_code": None,
                "error": "Run scripts/build_source_health_report.py to refresh source health.",
                "record_count": 0,
                "retryable": True,
            }
            for key in configured
        ]
        + [
            {
                "source_key": key,
                "attempted": False,
                "configured": False,
                "enabled": False,
                "ok": False,
                "status": "missing_configuration",
                "status_code": None,
                "error": "Source is not configured in the current environment.",
                "record_count": 0,
                "retryable": False,
            }
            for key in missing
        ],
        "usage_note": (
            "This endpoint serves the last cached source-health report only. It never calls external APIs, "
            "never triggers real-money betting, never submits picks, and never emits recommended bets or stake sizing."
        ),
    }


def first_existing_fixture_cache_path() -> Path | None:
    for path in FIXTURE_CACHE_PATHS:
        if path.exists():
            return path
    return None


def cached_fixture_snapshot() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Read the generated fixture cache and keep metadata for completeness reports."""

    first_existing_path = first_existing_fixture_cache_path()
    for path in FIXTURE_CACHE_PATHS:
        payload = load_json_file(path)
        records: list[Any]
        generated_at = utc_now()
        if isinstance(payload, dict):
            records = payload.get("fixtures", [])
            generated_at = payload.get("generated_at") or payload.get("synced_at") or generated_at
        elif isinstance(payload, list):
            records = payload
        else:
            records = []

        if isinstance(records, list) and records:
            return [record for record in records if isinstance(record, dict)], {
                "source_used": "cache",
                "generated_at": generated_at,
                "cache_path": str(path.relative_to(ROOT_DIR)),
                "cache_exists": True,
                "warnings": [],
            }

    cache_path = str(first_existing_path.relative_to(ROOT_DIR)) if first_existing_path else None
    return [], {
        "source_used": "cache_missing",
        "generated_at": utc_now(),
        "cache_path": cache_path,
        "cache_exists": bool(first_existing_path),
        "warnings": ["Fixture cache is missing or empty; run scripts/build_worldcup_fixture_cache.py."],
    }


def fixture_cache_status_report(tz: str = DEFAULT_FIXTURE_TIMEZONE) -> dict[str, Any]:
    cache_path = first_existing_fixture_cache_path()
    cache_exists = cache_path is not None
    report = load_json_file(WORLD_CUP_FIXTURE_CACHE_REPORT_PATH)

    if isinstance(report, dict):
        payload = {
            "cache_exists": cache_exists,
            "fixture_count": int(report.get("fixture_count") or 0),
            "completed_count": int(report.get("completed_count") or 0),
            "tomorrow_count": int(report.get("tomorrow_count") or 0),
            "scheduled_count": int(report.get("scheduled_count") or 0),
            "is_complete_worldcup_schedule": bool(report.get("is_complete_worldcup_schedule")) and cache_exists,
            "missing_reason": report.get("missing_reason"),
            "cache_path": report.get("cache_path") or (str(cache_path.relative_to(ROOT_DIR)) if cache_path else None),
            "generated_at": report.get("generated_at"),
            "source_used": report.get("source_used") or "worldcup_fixture_cache_report",
        }
        if not cache_exists:
            payload["missing_reason"] = payload["missing_reason"] or "cache_missing_in_runtime"
            payload["is_complete_worldcup_schedule"] = False
        return safe_payload(payload)

    records, metadata = cached_fixture_snapshot()
    fallback_payload = build_fixture_api_payload(
        records,
        source_used=metadata.get("source_used", "cache_missing"),
        generated_at=metadata.get("generated_at") or utc_now(),
        today=current_date_for_timezone(tz),
        tz=tz,
        cache_exists=bool(metadata.get("cache_exists")),
        cache_path=metadata.get("cache_path"),
        warnings=metadata.get("warnings", []),
    )
    completeness = fallback_payload["data_completeness"]
    return safe_payload(
        {
            "cache_exists": bool(completeness.get("cache_exists")),
            "fixture_count": completeness["fixture_count"],
            "completed_count": completeness["completed_count"],
            "tomorrow_count": completeness["tomorrow_count"],
            "scheduled_count": completeness["scheduled_count"],
            "is_complete_worldcup_schedule": completeness["is_complete_worldcup_schedule"],
            "missing_reason": completeness["missing_reason"] or "cache_report_missing",
            "cache_path": completeness.get("cache_path"),
            "generated_at": fallback_payload.get("generated_at"),
            "source_used": completeness["source_used"],
        }
    )


def cached_fixture_records() -> list[dict]:
    """Read pre-generated fixture snapshots without calling external APIs.

    Accepted payload formats:
    - {"fixtures": [...]} from ingestion/report scripts
    - [...] as a raw fixture list
    """

    records, _metadata = cached_fixture_snapshot()
    return records


def demo_fixture_records() -> list[dict[str, Any]]:
    return [to_plain_payload(fixture) for fixture in demo_fixtures()]


def fixture_product_records(source: str = "auto") -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if source == "cache":
        return cached_fixture_snapshot()
    if source == "demo":
        return demo_fixture_records(), {
            "source_used": "demo_fallback",
            "generated_at": utc_now(),
            "cache_path": None,
            "cache_exists": False,
            "warnings": ["Demo fallback requested explicitly; this is not a complete World Cup schedule."],
        }
    if source == "ingestion":
        checked_at = utc_now()
        try:
            payload = fixture_ingestion()
        except Exception as exc:  # noqa: BLE001 - product endpoint returns JSON fallback instead of crashing
            return [], {
                "source_used": "ingestion_failed",
                "generated_at": checked_at,
                "cache_path": None,
                "cache_exists": False,
                "warnings": [f"Fixture ingestion failed: {type(exc).__name__}"],
            }
        records = payload.get("fixtures", []) if isinstance(payload, dict) else []
        return [record for record in records if isinstance(record, dict)], {
            "source_used": "ingestion",
            "generated_at": payload.get("generated_at") or checked_at if isinstance(payload, dict) else checked_at,
            "cache_path": None,
            "cache_exists": False,
            "warnings": [],
        }
    if source == "auto":
        records, metadata = cached_fixture_snapshot()
        if records:
            return records, metadata
        return demo_fixture_records(), {
            "source_used": "demo_fallback",
            "generated_at": utc_now(),
            "cache_path": metadata.get("cache_path"),
            "cache_exists": bool(metadata.get("cache_exists")),
            "warnings": [
                "Fixture cache is missing or empty; serving demo fallback until cache is built.",
                "Demo fallback is not official production data.",
            ],
        }
    raise HTTPException(
        status_code=400,
        detail=api_error(
            "invalid_fixture_source",
            "source must be one of: auto, demo, cache, ingestion",
            {"source": source},
        ),
    )


def fixture_product_payload(
    *,
    source: str = "auto",
    status: str = "all",
    date_filter: str | None = None,
    target_date=None,
    stage: str | None = None,
    tz: str = DEFAULT_FIXTURE_TIMEZONE,
    limit: int | None = None,
) -> dict[str, Any]:
    records, metadata = fixture_product_records(source)
    try:
        payload = build_fixture_api_payload(
            records,
            source_used=metadata.get("source_used", source),
            generated_at=metadata.get("generated_at") or utc_now(),
            today=current_date_for_timezone(tz),
            status=status,
            date_filter=date_filter,
            target_date=target_date,
            stage=stage,
            tz=tz,
            limit=limit,
            warnings=metadata.get("warnings", []),
            cache_exists=bool(metadata.get("cache_exists")),
            cache_path=metadata.get("cache_path"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=api_error("invalid_fixture_filter", str(exc), {"status": status, "date": date_filter, "stage": stage}),
        ) from exc
    payload["cache_path"] = metadata.get("cache_path")
    return safe_payload(payload)


def record_team_name(record: dict, flat_key: str, nested_key: str) -> str | None:
    flat_value = record.get(flat_key)
    if isinstance(flat_value, str) and flat_value.strip():
        return flat_value.strip()

    nested_value = record.get(nested_key)
    if isinstance(nested_value, str) and nested_value.strip():
        return nested_value.strip()
    if isinstance(nested_value, dict):
        for key in ("name", "country", "id"):
            value = nested_value.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    return None


def fixture_records_to_fixtures(records: list[dict]) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for record in records:
        home_name = record_team_name(record, "home_team_name", "home_team")
        away_name = record_team_name(record, "away_team_name", "away_team")
        if not home_name or not away_name:
            continue
        fixtures.append(
            Fixture(
                id=record.get("id") or f"{normalize_name(home_name)}-{normalize_name(away_name)}",
                home_team=neutral_team(home_name),
                away_team=neutral_team(away_name),
                kickoff_time=record.get("kickoff_time") or "unknown",
                venue=record.get("venue"),
                stage=record.get("stage") or "unknown",
                status=record.get("status") or "scheduled",
                home_score=record.get("home_score"),
                away_score=record.get("away_score"),
            )
        )
    return fixtures


def cached_fixtures() -> list[Fixture]:
    return fixture_records_to_fixtures(cached_fixture_records())


def ingested_fixtures() -> list[Fixture]:
    payload = fixture_ingestion()
    return fixture_records_to_fixtures(payload.get("fixtures", []))


def fixtures_by_source(source: str = "auto") -> list[Fixture]:
    if source == "demo":
        return demo_fixtures()
    if source == "cache":
        return cached_fixtures()
    if source == "ingestion":
        return ingested_fixtures()
    if source == "auto":
        cached = cached_fixtures()
        return cached or demo_fixtures()
    raise HTTPException(
        status_code=400,
        detail=api_error(
            "invalid_fixture_source",
            "source must be one of: auto, demo, cache, ingestion",
            {"source": source},
        ),
    )


def match_feature_rows(source: str = "auto"):
    return build_match_feature_table(fixtures_by_source(source), source_context(), market_consensus=None)


def tournamental_odds():
    return TournamentalOddsClient(settings)


def tournamental_wc2026():
    return TournamentalWC2026Client(settings)


def normalized_market_snapshot() -> dict | None:
    result = tournamental_odds().snapshot()
    if not result.ok:
        return None
    return normalize_tournamental_snapshot(result.__dict__)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": settings.model_version}


@app.get("/data-sources", response_model=list[DataSourceStatus])
def data_sources() -> list[DataSourceStatus]:
    return safe_payload(canonical_data_source_statuses())


@app.get("/data-sources/canonical")
def data_sources_canonical():
    return safe_payload(canonical_source_registry())


@app.get("/data-sources/context")
def data_source_context():
    return safe_payload(source_context())


@app.get("/data-sources/health")
def data_sources_health():
    return safe_payload(source_health_report())


@app.get("/ingestion/fixtures")
def ingestion_fixtures():
    return safe_fixture_ingestion_report()


@app.get("/model/features")
def model_features():
    return safe_payload(advanced_feature_registry())


@app.get("/model/feature-table")
def model_feature_table(
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
):
    return safe_payload(match_feature_rows(source=source))


@app.get("/market/worldcup/health")
def worldcup_market_health():
    return safe_payload(tournamental_odds().health())


@app.get("/market/worldcup/snapshot")
def worldcup_market_snapshot():
    return safe_payload(tournamental_odds().snapshot())


@app.get("/market/worldcup/snapshot/normalized")
def worldcup_market_snapshot_normalized():
    normalized = normalized_market_snapshot()
    if normalized is None:
        return safe_payload(tournamental_odds().snapshot())
    return safe_payload(normalized)


@app.get("/market/worldcup/markets")
def worldcup_market_markets():
    return safe_payload(tournamental_odds().markets())


@app.get("/market/worldcup/match/{match_no}")
def worldcup_market_match(match_no: str):
    return safe_payload(tournamental_odds().match(match_no))


@app.get("/market/worldcup/team/{code}/winner")
def worldcup_market_team_winner(code: str):
    return safe_payload(tournamental_odds().team_winner(code))


@app.get("/market/worldcup/team/{code}/group")
def worldcup_market_team_group(code: str):
    return safe_payload(tournamental_odds().team_group(code))


@app.get("/wc2026/health")
def wc2026_health():
    return safe_payload(tournamental_wc2026().health())


@app.get("/wc2026/version")
def wc2026_version():
    return safe_payload(tournamental_wc2026().version())


@app.get("/wc2026/upcoming")
def wc2026_upcoming():
    return safe_payload(tournamental_wc2026().upcoming())


@app.get("/wc2026/match/{match_id}")
def wc2026_match(match_id: str):
    return safe_payload(tournamental_wc2026().match(match_id))


@app.get("/fixtures/cache/status")
def fixtures_cache_status(tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE)):
    return fixture_cache_status_report(tz=tz)


@app.get("/fixtures")
def list_fixtures(
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
    status: str = Query(default="all", description="completed, scheduled, live, or all"),
    date: str | None = Query(default=None, description="YYYY-MM-DD in the requested timezone"),
    stage: str | None = Query(default=None, description="Stage or group label, for example Group A"),
    tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE, description="IANA timezone, default Asia/Taipei"),
    limit: int | None = Query(default=None, ge=1),
):
    return fixture_product_payload(source=source, status=status, date_filter=date, stage=stage, tz=tz, limit=limit)


@app.get("/fixtures/completed")
def completed_fixtures(
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
    tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE),
    limit: int | None = Query(default=None, ge=1),
):
    return fixture_product_payload(source=source, status="completed", tz=tz, limit=limit)


@app.get("/fixtures/today")
def today_fixtures(
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
    tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE),
    limit: int | None = Query(default=None, ge=1),
):
    today = current_date_for_timezone(tz)
    return fixture_product_payload(source=source, status="all", target_date=today, tz=tz, limit=limit)


@app.get("/fixtures/tomorrow")
def tomorrow_fixtures(
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
    tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE),
    limit: int | None = Query(default=None, ge=1),
):
    tomorrow = current_date_for_timezone(tz) + timedelta(days=1)
    return fixture_product_payload(source=source, status="all", target_date=tomorrow, tz=tz, limit=limit)


@app.get("/fixtures/date/{fixture_date}")
def fixtures_for_date(
    fixture_date: str,
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
    status: str = Query(default="all", description="completed, scheduled, live, or all"),
    stage: str | None = Query(default=None),
    tz: str = Query(default=DEFAULT_FIXTURE_TIMEZONE),
    limit: int | None = Query(default=None, ge=1),
):
    return fixture_product_payload(
        source=source,
        status=status,
        date_filter=fixture_date,
        stage=stage,
        tz=tz,
        limit=limit,
    )


@app.get("/fixtures/{fixture_id}", response_model=Fixture)
def get_fixture(fixture_id: str, source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION)) -> Fixture:
    for fixture in fixtures_by_source(source):
        if fixture.id == fixture_id:
            return safe_payload(fixture)
    raise HTTPException(
        status_code=404,
        detail=api_error("fixture_not_found", "Fixture not found", {"fixture_id": fixture_id, "source": source}),
    )


@app.get("/predictions/{fixture_id}")
def get_prediction(
    fixture_id: str,
    source: str = Query(default="auto", description=FIXTURE_SOURCE_DESCRIPTION),
):
    fixture = get_fixture(fixture_id, source=source)
    if fixture.status.lower() in {"finished", "final", "full_time"}:
        raise HTTPException(
            status_code=409,
            detail=api_error(
                "fixture_finished",
                "Fixture is finished; use final score instead of prediction.",
                {"fixture_id": fixture_id},
            ),
        )
    market_snapshot = normalized_market_snapshot()
    market_signal = find_market_signal_for_fixture(fixture, market_snapshot) if market_snapshot else None
    service = PredictionService(model_version=settings.model_version)
    prediction = service.predict_fixture(
        fixture,
        source_context=source_context(),
        market_signal=market_signal,
    )
    return safe_payload(prediction)


@app.post("/predictions/manual")
def manual_prediction(payload: ManualPredictionInput):
    service = PredictionService(model_version=settings.model_version)
    fixture = Fixture(
        id=payload.fixture_id,
        home_team=payload.home_team,
        away_team=payload.away_team,
        kickoff_time=payload.kickoff_time,
    )
    return safe_payload(service.predict_fixture(fixture, source_context=payload.source_context))


@app.get("/model/performance", response_model=ModelPerformance)
def model_performance() -> ModelPerformance:
    return safe_payload(
        ModelPerformance(
            model_version=settings.model_version,
            matches_evaluated=0,
            accuracy=None,
            log_loss=None,
            brier_score=None,
        )
    )
