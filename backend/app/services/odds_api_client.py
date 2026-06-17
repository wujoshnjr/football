from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


class OddsApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class OddsApiQuota:
    requests_remaining: str | None
    requests_used: str | None
    requests_last: str | None


@dataclass(frozen=True)
class OddsApiResult:
    configured: bool
    endpoint: str
    sport_key: str | None
    count: int
    quota: dict[str, str | None]
    data: list[dict[str, Any]]


DEFAULT_SOCCER_SPORT_KEYS = [
    "soccer_usa_mls",
    "soccer_japan_j_league",
    "soccer_sweden_allsvenskan",
    "soccer_sweden_superettan",
    "soccer_norway_eliteserien",
    "soccer_finland_veikkausliiga",
    "soccer_brazil_campeonato",
]


class OddsApiClient:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "the_odds_api_key", None))

    def sports(self, include_all: bool = False) -> OddsApiResult:
        params: dict[str, str] = {"apiKey": self._api_key()}
        if include_all:
            params["all"] = "true"
        url = self._url("/sports", params)
        data, quota = self._get_json(url)
        return OddsApiResult(
            configured=True,
            endpoint="sports",
            sport_key=None,
            count=len(data) if isinstance(data, list) else 0,
            quota=asdict(quota),
            data=data if isinstance(data, list) else [],
        )

    def odds(
        self,
        sport_key: str | None = None,
        commence_time_from: str | None = None,
        commence_time_to: str | None = None,
    ) -> OddsApiResult:
        selected_sport = sport_key or getattr(self.settings, "the_odds_api_sport_key", "upcoming")
        params = {
            "apiKey": self._api_key(),
            "regions": getattr(self.settings, "the_odds_api_regions", "eu,uk,us"),
            "markets": getattr(self.settings, "the_odds_api_markets", "h2h"),
            "oddsFormat": getattr(self.settings, "the_odds_api_odds_format", "decimal"),
            "dateFormat": "iso",
        }
        if selected_sport != "upcoming":
            if commence_time_from:
                params["commenceTimeFrom"] = commence_time_from
            if commence_time_to:
                params["commenceTimeTo"] = commence_time_to
        url = self._url(f"/sports/{selected_sport}/odds", params)
        data, quota = self._get_json(url)
        return OddsApiResult(
            configured=True,
            endpoint="odds",
            sport_key=selected_sport,
            count=len(data) if isinstance(data, list) else 0,
            quota=asdict(quota),
            data=data if isinstance(data, list) else [],
        )

    def market_consensus(
        self,
        sport_key: str | None = None,
        commence_time_from: str | None = None,
        commence_time_to: str | None = None,
    ) -> dict[str, Any]:
        result = self.odds(
            sport_key=sport_key,
            commence_time_from=commence_time_from,
            commence_time_to=commence_time_to,
        )
        summaries = self._summaries_from_odds(result.data)
        return {
            "configured": result.configured,
            "sport_key": result.sport_key,
            "event_count": result.count,
            "quota": result.quota,
            "market_consensus": summaries,
            "usage_note": "Odds are used only as a market-consensus analysis signal. No betting execution is supported.",
        }

    def tomorrow_market_consensus(
        self,
        sport_keys: list[str] | None = None,
        timezone_name: str = "Asia/Taipei",
    ) -> dict[str, Any]:
        window = tomorrow_window(timezone_name)
        selected_sports = sport_keys or DEFAULT_SOCCER_SPORT_KEYS
        all_events: list[dict[str, Any]] = []
        source_results: list[dict[str, Any]] = []
        quota_snapshots: list[dict[str, str | None]] = []

        for sport_key in selected_sports:
            result = self.odds(
                sport_key=sport_key,
                commence_time_from=window["commence_time_from"],
                commence_time_to=window["commence_time_to"],
            )
            quota_snapshots.append(result.quota)
            source_results.append({
                "sport_key": sport_key,
                "event_count": result.count,
                "quota": result.quota,
            })
            all_events.extend(result.data)

        summaries = self._summaries_from_odds(all_events)
        summaries.sort(key=lambda item: item.get("commence_time") or "")
        return {
            "configured": True,
            "timezone": timezone_name,
            "local_date": window["local_date"],
            "commence_time_from": window["commence_time_from"],
            "commence_time_to": window["commence_time_to"],
            "sport_keys": selected_sports,
            "sport_count": len(selected_sports),
            "event_count": len(summaries),
            "quota": latest_quota(quota_snapshots),
            "sources": source_results,
            "market_consensus": summaries,
            "usage_note": "Tomorrow odds use league-specific soccer sport keys with a Taiwan-local tomorrow UTC time window. Odds are analysis signals only; no betting execution is supported.",
        }

    def _summaries_from_odds(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        summaries = []
        for event in events:
            h2h_prices: dict[str, list[float]] = {}
            for bookmaker in event.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name")
                        price = outcome.get("price")
                        if name is None or not isinstance(price, (int, float)) or price <= 1:
                            continue
                        h2h_prices.setdefault(name, []).append(float(price))

            consensus = {}
            for name, prices in h2h_prices.items():
                avg_decimal_odds = round(sum(prices) / len(prices), 4)
                consensus[name] = {
                    "average_decimal_odds": avg_decimal_odds,
                    "implied_probability": round(1 / avg_decimal_odds, 4),
                    "bookmaker_count": len(prices),
                }

            summaries.append({
                "event_id": event.get("id"),
                "sport_key": event.get("sport_key"),
                "commence_time": event.get("commence_time"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "bookmaker_count": len(event.get("bookmakers", [])),
                "market": "h2h",
                "consensus": consensus,
            })
        return summaries

    def _api_key(self) -> str:
        api_key = getattr(self.settings, "the_odds_api_key", None)
        if not api_key:
            raise OddsApiError("THE_ODDS_API_KEY is not configured")
        return api_key

    def _url(self, path: str, params: dict[str, str]) -> str:
        base_url = getattr(self.settings, "the_odds_api_base_url", "https://api.the-odds-api.com/v4").rstrip("/")
        safe_path = path if path.startswith("/") else f"/{path}"
        return f"{base_url}{safe_path}/?{urlencode(params)}"

    def _get_json(self, url: str) -> tuple[Any, OddsApiQuota]:
        request = Request(url, headers={"User-Agent": "football-prediction-odds-client/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                quota = OddsApiQuota(
                    requests_remaining=response.headers.get("x-requests-remaining"),
                    requests_used=response.headers.get("x-requests-used"),
                    requests_last=response.headers.get("x-requests-last"),
                )
                return json.loads(body), quota
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise OddsApiError(f"The Odds API HTTP {exc.code}: {details[:300]}") from exc
        except URLError as exc:
            raise OddsApiError(f"The Odds API network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise OddsApiError("The Odds API request timed out") from exc


def tomorrow_window(timezone_name: str = "Asia/Taipei") -> dict[str, str]:
    local_tz = ZoneInfo(timezone_name)
    local_now = datetime.now(local_tz)
    local_tomorrow = local_now.date() + timedelta(days=1)
    start_local = datetime.combine(local_tomorrow, datetime.min.time(), tzinfo=local_tz)
    end_local = start_local + timedelta(days=1) - timedelta(seconds=1)
    return {
        "local_date": local_tomorrow.isoformat(),
        "commence_time_from": to_utc_z(start_local),
        "commence_time_to": to_utc_z(end_local),
    }


def to_utc_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def latest_quota(items: list[dict[str, str | None]]) -> dict[str, str | None]:
    for item in reversed(items):
        if item:
            return item
    return {"requests_remaining": None, "requests_used": None, "requests_last": None}
