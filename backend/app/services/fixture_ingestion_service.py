from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
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
            self.openfootball_worldcup_json(),
            self.espn_scoreboard(),
        ]
        fixtures = dedupe_fixtures(record for result in results for record in result.records)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fixture_count": len(fixtures),
            "sources": [asdict(result) | {"records": []} for result in results],
            "fixtures": fixtures,
            "usage_note": "Ingested fixtures are normalized snapshots. They should be cross-checked before replacing demo fixtures as the default site source.",
        }

    def football_data_worldcup(self) -> SourceAdapterResult:
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

    def openfootball_worldcup_json(self) -> SourceAdapterResult:
        url = getattr(self.settings, "openfootball_worldcup_json_url", None)
        return self._json_adapter(
            source_key="openfootball_worldcup_json",
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

    def _json_adapter(self, source_key: str, url: str | None, normalizer) -> SourceAdapterResult:
        if not url:
            return SourceAdapterResult(source_key, False, False, None, "missing_url", 0, [])
        request = Request(url, headers={"User-Agent": "football-prediction-fixture-ingestion/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                records = normalizer(payload, source_key=source_key)
                return SourceAdapterResult(source_key, True, True, response.status, None, len(records), records)
        except HTTPError as exc:
            return SourceAdapterResult(source_key, True, False, exc.code, f"http_{exc.code}", 0, [])
        except URLError as exc:
            return SourceAdapterResult(source_key, True, False, None, str(exc.reason), 0, [])
        except TimeoutError:
            return SourceAdapterResult(source_key, True, False, None, "timeout", 0, [])
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return SourceAdapterResult(source_key, True, False, None, f"parse_error: {exc}", 0, [])


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
    priorities = {"football_data": 0, "espn_scoreboard": 1, "openfootball_worldcup_json": 2}
    return priorities.get(str(source_key), 99)


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
        return first_text(value, ["displayName", "name", "shortName", "shortDisplayName", "country", "code"])
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
