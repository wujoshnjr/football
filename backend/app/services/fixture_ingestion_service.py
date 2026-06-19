from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.services.football_data_client import FootballDataClient


@dataclass(frozen=True)
class SourceAdapterResult:
    source_key: str
    configured: bool
    ok: bool
    status_code: int | None
    error: str | None
    record_count: int
    records: list[dict[str, Any]]


class FixtureIngestionService:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    def ingest(self) -> dict[str, Any]:
        results = [
            self.football_data_worldcup(),
            self.api_football_worldcup(),
            self.thestatsapi_worldcup(),
            self.sportsdataio_worldcup(),
            self.worldcup_2026_public(),
            self.tournamental_wc2026(),
            self.zafronix_worldcup(),
            self.thesportsdb_worldcup(),
            self.openfootball_worldcup_json(),
            self.espn_scoreboard(),
            self.humhub_fwc_2026(),
            self.fifa_ranking_source(),
            self.open_meteo_weather(),
            self.gdelt_news(),
            self.statsbomb_open_data(),
        ]
        fixtures = dedupe_fixtures(record for result in results for record in result.records)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fixture_count": len(fixtures),
            "sources": [asdict(result) | {"records": []} for result in results],
            "fixtures": fixtures,
            "usage_note": (
                "Ingested fixtures are normalized snapshots. Weather, ranking, news, and offline training sources are "
                "reported as feature-source readiness only; they do not create fixtures. This pipeline never triggers "
                "real-money betting, recommended bets, stake sizing, or live betting."
            ),
        }

    def football_data_worldcup(self) -> SourceAdapterResult:
        if not bool(getattr(self.settings, "football_data_enabled", True)):
            configured = bool(getattr(self.settings, "football_data_token", None))
            return SourceAdapterResult("football_data", configured, False, None, "disabled", 0, [])
        result = FootballDataClient(self.settings, timeout_seconds=self.timeout_seconds).worldcup_matches()
        return SourceAdapterResult(
            source_key=result.source_key,
            configured=result.configured,
            ok=result.ok,
            status_code=result.status_code,
            error=result.error,
            record_count=result.record_count,
            records=result.records,
        )

    def api_football_worldcup(self) -> SourceAdapterResult:
        source_key = "api_football"
        if not bool(getattr(self.settings, "api_football_enabled", True)):
            configured = bool(getattr(self.settings, "api_football_key", None))
            return SourceAdapterResult(source_key, configured, False, None, "disabled", 0, [])
        key = getattr(self.settings, "api_football_key", None)
        base_url = getattr(self.settings, "api_football_base_url", None)
        if not key:
            return SourceAdapterResult(source_key, False, False, None, "missing_credentials", 0, [])
        url = build_url(
            base_url,
            "/fixtures",
            {
                "league": str(getattr(self.settings, "api_football_worldcup_league_id", 1)),
                "season": str(getattr(self.settings, "api_football_worldcup_season", 2026)),
            },
        )
        return self._json_adapter(
            source_key=source_key,
            url=url,
            normalizer=normalize_api_football_records,
            headers={"x-apisports-key": key},
            configured=True,
        )

    def thestatsapi_worldcup(self) -> SourceAdapterResult:
        source_key = "thestatsapi_worldcup"
        if not bool(getattr(self.settings, "thestatsapi_enabled", False)):
            configured = bool(getattr(self.settings, "thestatsapi_key", None))
            return SourceAdapterResult(source_key, configured, False, None, "disabled", 0, [])
        key = getattr(self.settings, "thestatsapi_key", None)
        competition_id = getattr(self.settings, "thestatsapi_world_cup_competition_id", None)
        season_id = getattr(self.settings, "thestatsapi_world_cup_season_id", None)
        if not key:
            return SourceAdapterResult(source_key, False, False, None, "missing_credentials", 0, [])
        if not competition_id or not season_id:
            return SourceAdapterResult(source_key, True, False, None, "missing_world_cup_ids", 0, [])
        url = build_url(
            getattr(self.settings, "thestatsapi_base_url", None),
            "/football/matches",
            {
                "competition_id": str(competition_id),
                "season_id": str(season_id),
                "page": "1",
                "per_page": "100",
            },
        )
        return self._json_adapter(
            source_key=source_key,
            url=url,
            normalizer=normalize_generic_fixture_records,
            headers={"Authorization": f"Bearer {key}", "Accept": "application/json"},
            configured=True,
        )

    def sportsdataio_worldcup(self) -> SourceAdapterResult:
        source_key = "sportsdataio_worldcup"
        if not bool(getattr(self.settings, "sportsdataio_enabled", False)):
            configured = bool(getattr(self.settings, "sportsdataio_api_key", None))
            return SourceAdapterResult(source_key, configured, False, None, "disabled", 0, [])
        key = getattr(self.settings, "sportsdataio_api_key", None)
        competition_id = (
            getattr(self.settings, "sportsdataio_world_cup_competition_id", None)
            or getattr(self.settings, "sportsdataio_world_cup_competition_key", None)
        )
        season_id = (
            getattr(self.settings, "sportsdataio_world_cup_season_id", None)
            or getattr(self.settings, "sportsdataio_world_cup_season", None)
        )
        if not key:
            return SourceAdapterResult(source_key, False, False, None, "missing_credentials", 0, [])
        if not competition_id or not season_id:
            return SourceAdapterResult(source_key, True, False, None, "missing_world_cup_ids", 0, [])
        path_template = getattr(
            self.settings,
            "sportsdataio_world_cup_fixtures_path",
            "/scores/json/GamesByCompetition/{competition_id}/{season_id}",
        )
        path = path_template.format(
            competition_key=competition_id,
            competition_id=competition_id,
            season=season_id,
            season_id=season_id,
        )
        return self._json_adapter(
            source_key=source_key,
            url=build_url(getattr(self.settings, "sportsdataio_base_url", None), path),
            normalizer=normalize_generic_fixture_records,
            headers={"Ocp-Apim-Subscription-Key": key, "Accept": "application/json"},
            configured=True,
        )

    def worldcup_2026_public(self) -> SourceAdapterResult:
        source_key = "worldcup_2026_api"
        base_url = getattr(self.settings, "worldcup_2026_public_base_url", None)
        if not bool(getattr(self.settings, "worldcup_2026_api_enabled", False)):
            return SourceAdapterResult(source_key, bool(base_url), False, None, "disabled", 0, [])
        return self._json_adapter(
            source_key=source_key,
            url=build_url(base_url, "/get/games"),
            normalizer=normalize_generic_fixture_records,
            configured=bool(base_url),
        )

    def tournamental_wc2026(self) -> SourceAdapterResult:
        source_key = "tournamental_wc2026"
        base_url = getattr(self.settings, "tournamental_wc2026_base_url", None)
        if not bool(getattr(self.settings, "tournamental_wc2026_enabled", True)):
            return SourceAdapterResult(source_key, bool(base_url), False, None, "disabled", 0, [])
        return self._json_adapter(
            source_key=source_key,
            url=build_url(base_url, "/v1/upcoming"),
            normalizer=normalize_generic_fixture_records,
            configured=bool(base_url),
        )

    def zafronix_worldcup(self) -> SourceAdapterResult:
        source_key = "zafronix_worldcup"
        if not bool(getattr(self.settings, "zafronix_worldcup_enabled", False)):
            configured = bool(getattr(self.settings, "zafronix_worldcup_key", None) and getattr(self.settings, "zafronix_worldcup_base_url", None))
            return SourceAdapterResult(source_key, configured, False, None, "disabled", 0, [])
        key = getattr(self.settings, "zafronix_worldcup_key", None)
        if not key:
            return SourceAdapterResult(source_key, False, False, None, "missing_credentials", 0, [])
        url = build_url(getattr(self.settings, "zafronix_worldcup_base_url", None), "/matches", {"year": "2026"})
        return self._json_adapter(
            source_key=source_key,
            url=url,
            normalizer=normalize_generic_fixture_records,
            headers={"X-API-Key": key, "Accept": "application/json"},
            configured=True,
        )

    def thesportsdb_worldcup(self) -> SourceAdapterResult:
        source_key = "thesportsdb_worldcup"
        api_key = getattr(self.settings, "thesportsdb_api_key", None)
        league_id = getattr(self.settings, "thesportsdb_world_cup_league_id", None)
        if not bool(getattr(self.settings, "thesportsdb_enabled", False)):
            return SourceAdapterResult(source_key, bool(api_key and league_id), False, None, "disabled", 0, [])
        if not api_key or not league_id:
            return SourceAdapterResult(source_key, False, False, None, "missing_api_key_or_league_id", 0, [])
        url = build_url(
            getattr(self.settings, "thesportsdb_base_url", None),
            f"/{api_key}/eventsseason.php",
            {
                "id": str(league_id),
                "s": str(getattr(self.settings, "thesportsdb_world_cup_season", "2026")),
            },
        )
        return self._json_adapter(
            source_key=source_key,
            url=url,
            normalizer=normalize_thesportsdb_records,
            configured=True,
        )

    def openfootball_worldcup_json(self) -> SourceAdapterResult:
        source_key = "openfootball_worldcup_json"
        if not bool(getattr(self.settings, "openfootball_worldcup_json_enabled", True)):
            return SourceAdapterResult(source_key, bool(getattr(self.settings, "openfootball_worldcup_json_url", None)), False, None, "disabled", 0, [])
        url = getattr(self.settings, "openfootball_worldcup_json_url", None)
        return self._json_adapter(
            source_key=source_key,
            url=url,
            normalizer=normalize_openfootball_records,
        )

    def espn_scoreboard(self) -> SourceAdapterResult:
        url = getattr(self.settings, "espn_scoreboard_url", None)
        return self._json_adapter(
            source_key="espn_scoreboard",
            url=url,
            normalizer=normalize_espn_scoreboard_records,
        )

    def humhub_fwc_2026(self) -> SourceAdapterResult:
        source_key = "humhub_fwc_2026"
        base_url = getattr(self.settings, "humhub_fwc_2026_base_url", None)
        if not bool(getattr(self.settings, "humhub_fwc_2026_enabled", False)):
            return SourceAdapterResult(source_key, bool(base_url), False, None, "disabled", 0, [])
        return self._json_adapter(
            source_key=source_key,
            url=build_url(base_url, "/matches"),
            normalizer=normalize_generic_fixture_records,
            configured=bool(base_url),
        )

    def fifa_ranking_source(self) -> SourceAdapterResult:
        return self._feature_source_result(
            source_key="fifa_ranking_source",
            configured=bool(getattr(self.settings, "fifa_ranking_url", None)),
            enabled=bool(getattr(self.settings, "fifa_ranking_enabled", False)),
        )

    def open_meteo_weather(self) -> SourceAdapterResult:
        return self._feature_source_result(
            source_key="open_meteo_weather",
            configured=bool(getattr(self.settings, "open_meteo_base_url", None)),
            enabled=bool(getattr(self.settings, "open_meteo_enabled", False)),
        )

    def gdelt_news(self) -> SourceAdapterResult:
        return self._feature_source_result(
            source_key="gdelt_news",
            configured=bool(getattr(self.settings, "gdelt_doc_base_url", None)),
            enabled=bool(getattr(self.settings, "gdelt_enabled", False)),
        )

    def statsbomb_open_data(self) -> SourceAdapterResult:
        return self._feature_source_result(
            source_key="statsbomb_open_data",
            configured=bool(getattr(self.settings, "statsbomb_open_data_base_url", None)),
            enabled=bool(getattr(self.settings, "statsbomb_open_data_enabled", True)),
        )

    def _feature_source_result(self, source_key: str, configured: bool, enabled: bool) -> SourceAdapterResult:
        if not enabled:
            return SourceAdapterResult(source_key, configured, False, None, "disabled", 0, [])
        if not configured:
            return SourceAdapterResult(source_key, False, False, None, "missing_url", 0, [])
        return SourceAdapterResult(source_key, True, True, None, "feature_source_not_fixture_ingestion", 0, [])

    def _json_adapter(
        self,
        source_key: str,
        url: str | None,
        normalizer: Callable[..., list[dict[str, Any]]],
        headers: dict[str, str] | None = None,
        configured: bool | None = None,
    ) -> SourceAdapterResult:
        is_configured = bool(url) if configured is None else configured
        if not url:
            return SourceAdapterResult(source_key, is_configured, False, None, "missing_url", 0, [])
        request_headers = {"User-Agent": "football-prediction-fixture-ingestion/1.0", "Accept": "application/json"}
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers)
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                records = normalizer(payload, source_key=source_key)
                status_error = None if records else "empty_response"
                return SourceAdapterResult(source_key, is_configured, bool(records), response.status, status_error, len(records), records)
        except HTTPError as exc:
            return SourceAdapterResult(source_key, is_configured, False, exc.code, normalize_http_error(exc.code), 0, [])
        except URLError as exc:
            return SourceAdapterResult(source_key, is_configured, False, None, str(exc.reason), 0, [])
        except TimeoutError:
            return SourceAdapterResult(source_key, is_configured, False, None, "timeout", 0, [])
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return SourceAdapterResult(source_key, is_configured, False, None, f"parse_error: {exc}", 0, [])


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
        records.append(make_fixture_record(
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
        ))
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
        records.append(make_fixture_record(
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
        ))
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
        records.append(make_fixture_record(
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
        ))
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
        records.append(make_fixture_record(
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
        ))
    return records


def normalize_generic_fixture_records(payload: Any, source_key: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in iter_dicts(payload):
        home = first_text(item, [
            "home_team", "homeTeam", "home", "team1", "team_1", "home_team_name",
            "homeName", "localteam", "localTeam", "team_home", "HomeTeamName", "HomeTeam",
        ])
        away = first_text(item, [
            "away_team", "awayTeam", "away", "team2", "team_2", "away_team_name",
            "awayName", "visitorteam", "visitorTeam", "team_away", "AwayTeamName", "AwayTeam",
        ])
        if not valid_team_pair(home, away):
            continue
        kickoff = first_text(item, [
            "kickoff_time", "kickoff", "datetime", "date", "time", "utcDate",
            "startTime", "start_time", "match_date", "game_date", "dateTime", "timestamp",
            "DateTime", "Day",
        ])
        home_score = first_int(item, [
            "home_score", "homeScore", "home_goals", "homeGoals", "goals_home",
            "score1", "score_1", "goals1", "homeTeamScore", "HomeTeamScore",
        ])
        away_score = first_int(item, [
            "away_score", "awayScore", "away_goals", "awayGoals", "goals_away",
            "score2", "score_2", "goals2", "awayTeamScore", "AwayTeamScore",
        ])
        records.append(make_fixture_record(
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
        ))
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


def build_url(base_url: str | None, path: str, params: dict[str, str] | None = None) -> str | None:
    if not base_url:
        return None
    base = base_url.rstrip("/")
    safe_path = path if path.startswith("/") else f"/{path}"
    query = f"?{urlencode(params)}" if params else ""
    return f"{base}{safe_path}{query}"


def normalize_http_error(status_code: int) -> str:
    if status_code in {401, 403}:
        return "unauthorized_or_forbidden"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "upstream_error"
    if status_code == 404:
        return "not_found"
    return f"http_{status_code}"


def normalize_status(status: str | None, home_score: int | None, away_score: int | None, elapsed: int | None = None) -> str:
    raw = (status or "").strip().lower()
    if home_score is not None and away_score is not None and raw in {"ft", "aet", "pen", "finished", "match finished", "final", "full time"}:
        return "finished"
    if raw in {"ft", "aet", "pen", "finished", "match finished", "final", "full time"}:
        return "finished"
    if raw in {"ns", "tbd", "scheduled", "not started", "pre", "preview"}:
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
        return first_text(value, [
            "displayName", "name", "shortName", "shortDisplayName", "country", "code",
            "Name", "TeamName", "teamName", "fullName",
        ])
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
