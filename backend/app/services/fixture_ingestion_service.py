from __future__ import annotations

import asyncio
import hashlib
import re
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Iterable, Type

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult
from app.services.sources.api_football import ApiFootballAdapter
from app.services.sources.espn import ESPNScoreboardAdapter
from app.services.sources.feature_sources import (
    FifaRankingSourceAdapter,
    GdeltNewsAdapter,
    OpenMeteoWeatherAdapter,
    StatsBombOpenDataAdapter,
)
from app.services.sources.football_data import FootballDataAdapter
from app.services.sources.humhub import HumHubFWC2026Adapter
from app.services.sources.openfootball import OpenFootballWorldCupAdapter
from app.services.sources.registry import build_source_adapters
from app.services.sources.sportsdataio import SportsDataIOAdapter
from app.services.sources.thesportsdb import TheSportsDBAdapter
from app.services.sources.thestatsapi import TheStatsApiAdapter
from app.services.sources.tournamental_bot_arena import TournamentalBotArenaAdapter
from app.services.sources.tournamental_wc2026 import TournamentalWC2026Adapter
from app.services.sources.worldcup_2026_api import WorldCup2026ApiAdapter
from app.services.sources.zafronix import ZafronixWorldCupAdapter


class FixtureIngestionService:
    """Coordinate fixture ingestion through the new source adapter package.

    The public ``ingest()`` method remains synchronous for backwards compatibility with
    existing FastAPI routes and scripts. It now delegates network calls to the adapter
    layer under ``app.services.sources``. Feature, ranking, weather, news, market, and
    benchmark sources are reported for readiness but never create fixtures.
    """

    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    def ingest(self) -> dict[str, Any]:
        return asyncio.run(self.ingest_async())

    async def ingest_async(self) -> dict[str, Any]:
        adapters = build_source_adapters(self.settings, timeout_seconds=self.timeout_seconds)
        results = [await self._safe_fetch(adapter) for adapter in adapters]

        normalized_by_source: dict[str, list[dict[str, Any]]] = {}
        source_reports: list[dict[str, Any]] = []

        for adapter, result in zip(adapters, results, strict=False):
            normalized_records: list[dict[str, Any]] = []
            if adapter.produces_fixtures and result.ok:
                normalized_records = normalize_adapter_records(result.source_key, result.records)

            normalized_by_source[result.source_key] = normalized_records
            report = result.to_report_dict(include_records=False)
            report.update(
                {
                    "produces_fixtures": bool(adapter.produces_fixtures),
                    "raw_record_count": result.record_count,
                    "normalized_record_count": len(normalized_records),
                }
            )
            if adapter.produces_fixtures and result.ok and result.record_count > 0 and not normalized_records:
                report.update(
                    {
                        "ok": False,
                        "status": "schema_mismatch",
                        "error": "no_normalized_fixture_records",
                        "retryable": False,
                    }
                )
            source_reports.append(report)

        fixtures = dedupe_fixtures(
            record
            for adapter, result in zip(adapters, results, strict=False)
            if adapter.produces_fixtures
            for record in normalized_by_source.get(result.source_key, [])
        )
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fixture_count": len(fixtures),
            "sources": source_reports,
            "fixtures": fixtures,
            "usage_note": (
                "Ingested fixtures are normalized snapshots built through app.services.sources adapters. "
                "Weather, ranking, news, market, Tournamental Bot Arena, and offline training sources are reported "
                "as feature, benchmark, or market readiness only; they do not create fixtures. This pipeline never "
                "triggers real-money betting, recommended bets, stake sizing, pick submission, or live betting."
            ),
        }

    def run_health_checks(self) -> list[SourceAdapterResult]:
        return asyncio.run(self.run_health_checks_async())

    async def run_health_checks_async(self) -> list[SourceAdapterResult]:
        adapters = build_source_adapters(self.settings, timeout_seconds=self.timeout_seconds)
        return [await self._safe_fetch(adapter) for adapter in adapters]

    async def _safe_fetch(self, adapter: BaseSourceAdapter) -> SourceAdapterResult:
        try:
            return await adapter.fetch()
        except Exception as exc:  # noqa: BLE001 - ingestion reports errors instead of crashing
            return adapter.result(
                attempted=True,
                configured=True,
                enabled=True,
                ok=False,
                status="adapter_exception",
                error=str(exc),
                record_count=0,
                records=[],
                retryable=False,
                generated_at=datetime.now(timezone.utc).isoformat(),
            )

    def _fetch_single(self, adapter_cls: Type[BaseSourceAdapter]) -> SourceAdapterResult:
        result = asyncio.run(adapter_cls(self.settings, timeout_seconds=self.timeout_seconds).fetch())
        return legacy_error_compatible(result)

    # Backwards-compatible wrappers used by existing tests and callers.
    def football_data_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(FootballDataAdapter)

    def api_football_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(ApiFootballAdapter)

    def thestatsapi_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(TheStatsApiAdapter)

    def sportsdataio_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(SportsDataIOAdapter)

    def worldcup_2026_public(self) -> SourceAdapterResult:
        return self._fetch_single(WorldCup2026ApiAdapter)

    def tournamental_wc2026(self) -> SourceAdapterResult:
        return self._fetch_single(TournamentalWC2026Adapter)

    def zafronix_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(ZafronixWorldCupAdapter)

    def thesportsdb_worldcup(self) -> SourceAdapterResult:
        return self._fetch_single(TheSportsDBAdapter)

    def openfootball_worldcup_json(self) -> SourceAdapterResult:
        return self._fetch_single(OpenFootballWorldCupAdapter)

    def espn_scoreboard(self) -> SourceAdapterResult:
        return self._fetch_single(ESPNScoreboardAdapter)

    def humhub_fwc_2026(self) -> SourceAdapterResult:
        return self._fetch_single(HumHubFWC2026Adapter)

    def fifa_ranking_source(self) -> SourceAdapterResult:
        return self._fetch_single(FifaRankingSourceAdapter)

    def open_meteo_weather(self) -> SourceAdapterResult:
        return self._fetch_single(OpenMeteoWeatherAdapter)

    def gdelt_news(self) -> SourceAdapterResult:
        return self._fetch_single(GdeltNewsAdapter)

    def tournamental_bot_arena(self) -> SourceAdapterResult:
        return self._fetch_single(TournamentalBotArenaAdapter)

    def statsbomb_open_data(self) -> SourceAdapterResult:
        return self._fetch_single(StatsBombOpenDataAdapter)


def legacy_error_compatible(result: SourceAdapterResult) -> SourceAdapterResult:
    """Preserve older tests/callers that used ``error`` as the status string."""

    if result.error or result.status in {"ok", "unknown"}:
        return result
    return replace(result, error=result.status)


def normalize_adapter_records(source_key: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if source_key == "football_data":
        return normalize_football_data_records(records, source_key=source_key)
    if source_key == "api_football":
        return normalize_api_football_records({"response": records}, source_key=source_key)
    if source_key == "openfootball_worldcup_json":
        return normalize_openfootball_records(records, source_key=source_key)
    if source_key == "espn_scoreboard":
        return normalize_espn_scoreboard_records({"events": records}, source_key=source_key)
    if source_key == "thesportsdb_worldcup":
        return normalize_thesportsdb_records({"events": records}, source_key=source_key)
    return normalize_generic_fixture_records(records, source_key=source_key)


def normalize_football_data_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    items = payload.get("matches", []) if isinstance(payload, dict) else payload
    records: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        home = first_text(item, ["homeTeam", "home_team", "home"])
        away = first_text(item, ["awayTeam", "away_team", "away"])
        if not valid_team_pair(home, away):
            continue
        score = item.get("score", {}) if isinstance(item.get("score"), dict) else {}
        full_time = score.get("fullTime", {}) if isinstance(score.get("fullTime"), dict) else {}
        half_time = score.get("halfTime", {}) if isinstance(score.get("halfTime"), dict) else {}
        home_score = safe_int(full_time.get("home"))
        away_score = safe_int(full_time.get("away"))
        if home_score is None:
            home_score = safe_int(half_time.get("home"))
        if away_score is None:
            away_score = safe_int(half_time.get("away"))
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=item.get("id"),
                home_team=home,
                away_team=away,
                kickoff_time=first_text(item, ["utcDate", "date", "kickoff_time"]),
                venue=first_text(item, ["venue", "stadium"]),
                stage=first_text(item, ["stage", "group", "matchday", "round"]) or "world_cup",
                status=normalize_status(first_text(item, ["status"]), home_score, away_score),
                home_score=home_score,
                away_score=away_score,
            )
        )
    return records


def normalize_openfootball_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in iter_dicts(payload):
        home = first_text(item, ["home_team", "homeTeam", "home", "team1", "team_1"])
        away = first_text(item, ["away_team", "awayTeam", "away", "team2", "team_2"])
        if not valid_team_pair(home, away):
            continue
        kickoff = first_text(item, ["kickoff_time", "kickoff", "datetime", "date", "time", "utcDate"])
        stage = first_text(item, ["stage", "round", "group", "name"]) or "unknown"
        venue = first_text(item, ["venue", "stadium", "ground"])
        home_score = first_int(item, ["home_score", "homeScore", "score1", "score_1", "goals1"])
        away_score = first_int(item, ["away_score", "awayScore", "score2", "score_2", "goals2"])
        status = "finished" if home_score is not None and away_score is not None else "scheduled"
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=first_text(item, ["id", "key", "num"]),
                home_team=home,
                away_team=away,
                kickoff_time=kickoff,
                venue=venue,
                stage=stage,
                status=status,
                home_score=home_score,
                away_score=away_score,
            )
        )
    return records


def normalize_espn_scoreboard_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    events = payload.get("events", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        competition = first_dict(event.get("competitions", []))
        competitors = competition.get("competitors", []) if competition else []
        home_comp = find_espn_competitor(competitors, "home")
        away_comp = find_espn_competitor(competitors, "away")
        if not home_comp or not away_comp:
            continue
        home = first_text(home_comp.get("team", {}), ["displayName", "name", "shortDisplayName"])
        away = first_text(away_comp.get("team", {}), ["displayName", "name", "shortDisplayName"])
        if not valid_team_pair(home, away):
            continue
        status_type = event.get("status", {}).get("type", {}) if isinstance(event.get("status"), dict) else {}
        is_completed = bool(status_type.get("completed"))
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=event.get("id"),
                home_team=home,
                away_team=away,
                kickoff_time=event.get("date"),
                venue=first_text(competition.get("venue", {}) if competition else {}, ["fullName", "name"]),
                stage=first_text(event.get("season", {}) if isinstance(event.get("season"), dict) else {}, ["slug", "type"]) or "scoreboard",
                status="finished" if is_completed else status_type.get("state") or "scheduled",
                home_score=safe_int(home_comp.get("score")) if is_completed else None,
                away_score=safe_int(away_comp.get("score")) if is_completed else None,
            )
        )
    return records


def normalize_api_football_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    items = payload.get("response", []) if isinstance(payload, dict) else payload
    records: list[dict[str, Any]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        fixture = item.get("fixture", {}) if isinstance(item.get("fixture"), dict) else {}
        teams = item.get("teams", {}) if isinstance(item.get("teams"), dict) else {}
        goals = item.get("goals", {}) if isinstance(item.get("goals"), dict) else {}
        league = item.get("league", {}) if isinstance(item.get("league"), dict) else {}
        home = first_text(teams.get("home", {}), ["name", "displayName", "shortName"])
        away = first_text(teams.get("away", {}), ["name", "displayName", "shortName"])
        if not valid_team_pair(home, away):
            continue
        status_payload = fixture.get("status", {}) if isinstance(fixture.get("status"), dict) else {}
        elapsed = safe_int(status_payload.get("elapsed"))
        home_score = safe_int(goals.get("home"))
        away_score = safe_int(goals.get("away"))
        status_text = first_text(status_payload, ["short", "long"]) or "scheduled"
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=fixture.get("id"),
                home_team=home,
                away_team=away,
                kickoff_time=fixture.get("date"),
                venue=first_text(fixture.get("venue", {}) if isinstance(fixture.get("venue"), dict) else {}, ["name"]),
                stage=first_text(league, ["round", "name"]) or "world_cup",
                status=normalize_status(status_text, home_score, away_score, elapsed),
                home_score=home_score,
                away_score=away_score,
            )
        )
    return records


def normalize_thesportsdb_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    events = []
    if isinstance(payload, dict):
        events = payload.get("events") or payload.get("event") or []
    records: list[dict[str, Any]] = []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        home = first_text(event, ["strHomeTeam", "home_team", "homeTeam"])
        away = first_text(event, ["strAwayTeam", "away_team", "awayTeam"])
        if not valid_team_pair(home, away):
            continue
        date = first_text(event, ["strTimestamp", "dateEvent", "dateEventLocal"])
        time = first_text(event, ["strTime", "strTimeLocal"])
        kickoff = date
        if date and time and "T" not in date:
            kickoff = f"{date}T{time}"
        home_score = first_int(event, ["intHomeScore", "home_score", "homeScore"])
        away_score = first_int(event, ["intAwayScore", "away_score", "awayScore"])
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=first_text(event, ["idEvent", "id", "event_id"]),
                home_team=home,
                away_team=away,
                kickoff_time=kickoff,
                venue=first_text(event, ["strVenue", "venue", "stadium"]),
                stage=first_text(event, ["intRound", "strRound", "strGroup", "stage"]) or "world_cup",
                status=normalize_status(first_text(event, ["strStatus", "status"]), home_score, away_score),
                home_score=home_score,
                away_score=away_score,
            )
        )
    return records


def normalize_generic_fixture_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in iter_dicts(payload):
        home = first_text(
            item,
            [
                "home_team",
                "homeTeam",
                "home",
                "team1",
                "team_1",
                "home_team_name",
                "homeName",
                "localteam",
                "localTeam",
                "team_home",
                "HomeTeamName",
                "HomeTeam",
            ],
        )
        away = first_text(
            item,
            [
                "away_team",
                "awayTeam",
                "away",
                "team2",
                "team_2",
                "away_team_name",
                "awayName",
                "visitorteam",
                "visitorTeam",
                "team_away",
                "AwayTeamName",
                "AwayTeam",
            ],
        )
        if not valid_team_pair(home, away):
            continue
        kickoff = first_text(
            item,
            [
                "kickoff_time",
                "kickoff",
                "datetime",
                "date",
                "time",
                "utcDate",
                "startTime",
                "start_time",
                "match_date",
                "game_date",
                "dateTime",
                "timestamp",
                "DateTime",
                "Day",
            ],
        )
        home_score = first_int(
            item,
            [
                "home_score",
                "homeScore",
                "home_goals",
                "homeGoals",
                "goals_home",
                "score1",
                "score_1",
                "goals1",
                "homeTeamScore",
                "HomeTeamScore",
            ],
        )
        away_score = first_int(
            item,
            [
                "away_score",
                "awayScore",
                "away_goals",
                "awayGoals",
                "goals_away",
                "score2",
                "score_2",
                "goals2",
                "awayTeamScore",
                "AwayTeamScore",
            ],
        )
        records.append(
            make_fixture_record(
                source_key=source_key,
                source_event_id=first_text(item, ["id", "key", "num", "match_id", "matchId", "event_id", "eventId", "game_id", "GameId"]),
                home_team=home,
                away_team=away,
                kickoff_time=kickoff,
                venue=first_text(item, ["venue", "stadium", "ground", "location", "Venue", "Stadium"]),
                stage=first_text(item, ["stage", "round", "group", "name", "phase", "Round", "Group"]) or "world_cup",
                status=normalize_status(first_text(item, ["status", "state", "matchStatus", "gameStatus", "Status"]), home_score, away_score),
                home_score=home_score,
                away_score=away_score,
            )
        )
    return records


def make_fixture_record(
    source_key: str,
    source_event_id: Any,
    home_team: str,
    away_team: str,
    kickoff_time: str | None,
    venue: str | None,
    stage: str,
    status: str,
    home_score: int | None,
    away_score: int | None,
) -> dict[str, Any]:
    natural_id = "|".join([source_key, normalize_name(home_team), normalize_name(away_team), kickoff_time or "unknown"])
    return {
        "id": stable_id(natural_id),
        "source_key": source_key,
        "source_event_id": str(source_event_id) if source_event_id is not None else None,
        "home_team_name": home_team,
        "away_team_name": away_team,
        "kickoff_time": kickoff_time,
        "venue": venue,
        "stage": stage,
        "status": status,
        "home_score": home_score,
        "away_score": away_score,
        "match_key": f"{normalize_name(home_team)}__{normalize_name(away_team)}",
    }


def dedupe_fixtures(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str | None], dict[str, Any]] = {}
    for record in records:
        key = (record.get("match_key", ""), record.get("kickoff_time"))
        current = seen.get(key)
        if current is None or source_priority(record.get("source_key")) < source_priority(current.get("source_key")):
            seen[key] = record
    return sorted(seen.values(), key=lambda item: (str(item.get("kickoff_time") or "9999"), item.get("home_team_name") or ""))


def source_priority(source_key: Any) -> int:
    priorities = {
        "football_data": 0,
        "api_football": 1,
        "thestatsapi_worldcup": 2,
        "sportsdataio_worldcup": 3,
        "worldcup_2026_api": 4,
        "tournamental_wc2026": 5,
        "zafronix_worldcup": 6,
        "espn_scoreboard": 7,
        "openfootball_worldcup_json": 8,
        "thesportsdb_worldcup": 9,
        "humhub_fwc_2026": 10,
    }
    return priorities.get(str(source_key), 99)


def normalize_status(status: str | None, home_score: int | None, away_score: int | None, elapsed: int | None = None) -> str:
    raw = (status or "").strip().lower()
    if home_score is not None and away_score is not None and raw in {"ft", "aet", "pen", "finished", "match finished", "final", "full time"}:
        return "finished"
    if raw in {"ft", "aet", "pen", "finished", "match finished", "final", "full time"}:
        return "finished"
    if raw in {"ns", "tbd", "scheduled", "not started", "pre", "preview", "timed"}:
        return "scheduled"
    if raw in {"1h", "2h", "ht", "et", "bt", "live", "in progress", "in_play"} or elapsed:
        return "in_progress"
    if raw in {"pst", "postponed"}:
        return "postponed"
    if raw in {"canc", "cancelled", "canceled"}:
        return "cancelled"
    return raw or ("finished" if home_score is not None and away_score is not None else "scheduled")


def iter_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def first_text(item: Any, keys: list[str]) -> str | None:
    if not isinstance(item, dict):
        return None
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
    if isinstance(value, dict):
        return first_text(
            value,
            [
                "displayName",
                "name",
                "shortName",
                "shortDisplayName",
                "country",
                "code",
                "Name",
                "TeamName",
                "teamName",
                "fullName",
            ],
        )
    return None


def first_int(item: Any, keys: list[str]) -> int | None:
    if not isinstance(item, dict):
        return None
    for key in keys:
        if key in item:
            value = safe_int(item[key])
            if value is not None:
                return value
    return None


def first_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    return None


def find_espn_competitor(competitors: list[Any], home_away: str) -> dict[str, Any] | None:
    for competitor in competitors:
        if isinstance(competitor, dict) and competitor.get("homeAway") == home_away:
            return competitor
    return None


def valid_team_pair(home: str | None, away: str | None) -> bool:
    if not home or not away:
        return False
    if normalize_name(home) == normalize_name(away):
        return False
    return True


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "unknown"


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]
