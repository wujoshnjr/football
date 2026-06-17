from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ApiFootballError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiFootballResult:
    source_key: str
    configured: bool
    ok: bool
    status_code: int | None
    error: str | None
    record_count: int
    records: list[dict[str, Any]]


class ApiFootballClient:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "api_football_key", None))

    def worldcup_fixtures(
        self,
        league_id: int | None = None,
        season: int | None = None,
        date: str | None = None,
    ) -> ApiFootballResult:
        if not self.configured:
            return ApiFootballResult("api_football", False, False, None, "missing_key", 0, [])
        selected_league = league_id or getattr(self.settings, "api_football_worldcup_league_id", 1)
        selected_season = season or getattr(self.settings, "api_football_worldcup_season", 2026)
        params: dict[str, str] = {"league": str(selected_league), "season": str(selected_season)}
        if date:
            params["date"] = date
        try:
            payload, status_code = self._get_json("/fixtures", params=params)
            records = normalize_api_football_fixtures(payload)
            return ApiFootballResult("api_football", True, True, status_code, None, len(records), records)
        except ApiFootballError as exc:
            return ApiFootballResult("api_football", True, False, None, str(exc), 0, [])

    def worldcup_lineups(self, fixture_id: int | str) -> ApiFootballResult:
        if not self.configured:
            return ApiFootballResult("api_football_lineups", False, False, None, "missing_key", 0, [])
        try:
            payload, status_code = self._get_json("/fixtures/lineups", params={"fixture": str(fixture_id)})
            rows = payload.get("response", []) if isinstance(payload, dict) else []
            return ApiFootballResult("api_football_lineups", True, True, status_code, None, len(rows), rows)
        except ApiFootballError as exc:
            return ApiFootballResult("api_football_lineups", True, False, None, str(exc), 0, [])

    def worldcup_injuries(self, fixture_id: int | str | None = None) -> ApiFootballResult:
        if not self.configured:
            return ApiFootballResult("api_football_injuries", False, False, None, "missing_key", 0, [])
        params = {"fixture": str(fixture_id)} if fixture_id is not None else {}
        try:
            payload, status_code = self._get_json("/injuries", params=params)
            rows = payload.get("response", []) if isinstance(payload, dict) else []
            return ApiFootballResult("api_football_injuries", True, True, status_code, None, len(rows), rows)
        except ApiFootballError as exc:
            return ApiFootballResult("api_football_injuries", True, False, None, str(exc), 0, [])

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> tuple[Any, int | None]:
        token = getattr(self.settings, "api_football_key", None)
        if not token:
            raise ApiFootballError("API_FOOTBALL_KEY is not configured")
        url = self._url(path, params or {})
        request = Request(url, headers={"x-apisports-key": token, "User-Agent": "football-worldcup-api-football-client/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                api_errors = payload.get("errors") if isinstance(payload, dict) else None
                if api_errors:
                    raise ApiFootballError(f"API-Football returned errors: {api_errors}")
                return payload, response.status
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise ApiFootballError(f"API-Football HTTP {exc.code}: {details[:240]}") from exc
        except URLError as exc:
            raise ApiFootballError(f"API-Football network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ApiFootballError("API-Football request timed out") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise ApiFootballError(f"API-Football parse error: {exc}") from exc

    def _url(self, path: str, params: dict[str, str]) -> str:
        base_url = getattr(self.settings, "api_football_base_url", "https://v3.football.api-sports.io").rstrip("/")
        safe_path = path if path.startswith("/") else f"/{path}"
        query = f"?{urlencode(params)}" if params else ""
        return f"{base_url}{safe_path}{query}"


def normalize_api_football_fixtures(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("response", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        fixture = row.get("fixture", {}) if isinstance(row.get("fixture"), dict) else {}
        league = row.get("league", {}) if isinstance(row.get("league"), dict) else {}
        teams = row.get("teams", {}) if isinstance(row.get("teams"), dict) else {}
        goals = row.get("goals", {}) if isinstance(row.get("goals"), dict) else {}
        venue = fixture.get("venue", {}) if isinstance(fixture.get("venue"), dict) else {}
        status = fixture.get("status", {}) if isinstance(fixture.get("status"), dict) else {}
        home_team = team_name(teams.get("home"))
        away_team = team_name(teams.get("away"))
        if not home_team or not away_team:
            continue
        home_score = safe_int(goals.get("home"))
        away_score = safe_int(goals.get("away"))
        status_short = str(status.get("short") or status.get("long") or "scheduled").lower()
        records.append({
            "id": f"api-football-{fixture.get('id')}",
            "source_key": "api_football",
            "source_event_id": str(fixture.get("id")) if fixture.get("id") is not None else None,
            "home_team_name": home_team,
            "away_team_name": away_team,
            "kickoff_time": fixture.get("date"),
            "venue": venue.get("name"),
            "stage": str(league.get("round") or "world_cup"),
            "status": "finished" if status_short in {"ft", "aet", "pen", "match finished", "finished"} else status_short,
            "home_score": home_score,
            "away_score": away_score,
            "match_key": f"{normalize_name(home_team)}__{normalize_name(away_team)}",
            "league": league,
            "fixture_raw_status": status,
            "fixture_timestamp": fixture.get("timestamp"),
        })
    return records


def team_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    item = value.get("name")
    return item.strip() if isinstance(item, str) and item.strip() else None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
