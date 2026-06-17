from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class FootballDataError(RuntimeError):
    pass


@dataclass(frozen=True)
class FootballDataResult:
    source_key: str
    configured: bool
    ok: bool
    status_code: int | None
    error: str | None
    record_count: int
    records: list[dict[str, Any]]


class FootballDataClient:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "football_data_token", None))

    def worldcup_matches(
        self,
        competition_code: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> FootballDataResult:
        if not self.configured:
            return FootballDataResult("football_data", False, False, None, "missing_token", 0, [])
        selected_competition = competition_code or getattr(self.settings, "football_data_worldcup_competition_code", "WC")
        params: dict[str, str] = {}
        if date_from:
            params["dateFrom"] = date_from
        if date_to:
            params["dateTo"] = date_to
        path = f"/competitions/{selected_competition}/matches"
        try:
            payload, status_code = self._get_json(path, params=params)
            records = normalize_football_data_matches(payload)
            return FootballDataResult("football_data", True, True, status_code, None, len(records), records)
        except FootballDataError as exc:
            return FootballDataResult("football_data", True, False, None, str(exc), 0, [])

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> tuple[Any, int | None]:
        token = getattr(self.settings, "football_data_token", None)
        if not token:
            raise FootballDataError("FOOTBALL_DATA_TOKEN is not configured")
        url = self._url(path, params or {})
        request = Request(url, headers={"X-Auth-Token": token, "User-Agent": "football-worldcup-client/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8")), response.status
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise FootballDataError(f"football-data.org HTTP {exc.code}: {details[:240]}") from exc
        except URLError as exc:
            raise FootballDataError(f"football-data.org network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise FootballDataError("football-data.org request timed out") from exc
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise FootballDataError(f"football-data.org parse error: {exc}") from exc

    def _url(self, path: str, params: dict[str, str]) -> str:
        base_url = getattr(self.settings, "football_data_base_url", "https://api.football-data.org/v4").rstrip("/")
        safe_path = path if path.startswith("/") else f"/{path}"
        query = f"?{urlencode(params)}" if params else ""
        return f"{base_url}{safe_path}{query}"


def normalize_football_data_matches(payload: Any) -> list[dict[str, Any]]:
    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    records: list[dict[str, Any]] = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        home_team = team_name(match.get("homeTeam"))
        away_team = team_name(match.get("awayTeam"))
        if not home_team or not away_team:
            continue
        score = match.get("score", {}) if isinstance(match.get("score"), dict) else {}
        full_time = score.get("fullTime", {}) if isinstance(score.get("fullTime"), dict) else {}
        home_score = safe_int(full_time.get("home"))
        away_score = safe_int(full_time.get("away"))
        status = str(match.get("status") or "SCHEDULED").lower()
        records.append({
            "id": f"football-data-{match.get('id')}",
            "source_key": "football_data",
            "source_event_id": str(match.get("id")) if match.get("id") is not None else None,
            "home_team_name": home_team,
            "away_team_name": away_team,
            "kickoff_time": match.get("utcDate"),
            "venue": None,
            "stage": str(match.get("stage") or match.get("group") or "world_cup"),
            "status": "finished" if status in {"finished", "awarded"} or (home_score is not None and away_score is not None) else status,
            "home_score": home_score,
            "away_score": away_score,
            "match_key": f"{normalize_name(home_team)}__{normalize_name(away_team)}",
            "competition": match.get("competition"),
            "season": match.get("season"),
            "matchday": match.get("matchday"),
            "group": match.get("group"),
        })
    return records


def team_name(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in ("name", "shortName", "tla"):
        item = value.get(key)
        if isinstance(item, str) and item.strip():
            return item.strip()
    return None


def safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_name(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
