from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class TournamentalOddsError(RuntimeError):
    pass


@dataclass(frozen=True)
class TournamentalOddsResult:
    source_key: str
    configured: bool
    ok: bool
    status_code: int | None
    error: str | None
    record_count: int
    data: Any


class TournamentalOddsClient:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "tournamental_odds_base_url", None))

    def health(self) -> TournamentalOddsResult:
        return self._safe_get("health", "/healthz")

    def snapshot(self) -> TournamentalOddsResult:
        return self._safe_get("snapshot", "/v1/odds/snapshot")

    def markets(self) -> TournamentalOddsResult:
        return self._safe_get("markets", "/v1/odds/markets")

    def match(self, match_no: str | int) -> TournamentalOddsResult:
        safe_match_no = quote(str(match_no), safe="")
        return self._safe_get("match", f"/v1/odds/match/{safe_match_no}")

    def team_winner(self, code: str) -> TournamentalOddsResult:
        safe_code = quote(code.upper(), safe="")
        return self._safe_get("team_winner", f"/v1/odds/team/{safe_code}/winner")

    def team_group(self, code: str) -> TournamentalOddsResult:
        safe_code = quote(code.upper(), safe="")
        return self._safe_get("team_group", f"/v1/odds/team/{safe_code}/group")

    def _safe_get(self, label: str, path: str) -> TournamentalOddsResult:
        if not self.configured:
            return TournamentalOddsResult("tournamental_odds", False, False, None, "missing_base_url", 0, None)
        try:
            payload, status_code = self._get_json(path)
            count = len(payload) if isinstance(payload, list) else len(payload.keys()) if isinstance(payload, dict) else 1
            return TournamentalOddsResult("tournamental_odds", True, True, status_code, None, count, payload)
        except TournamentalOddsError as exc:
            return TournamentalOddsResult("tournamental_odds", True, False, None, f"{label}: {exc}", 0, None)

    def _get_json(self, path: str) -> tuple[Any, int | None]:
        url = self._url(path)
        request = Request(url, headers={"User-Agent": "football-worldcup-tournamental-odds-client/1.0"})
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                if not body:
                    return {"ok": True}, response.status
                try:
                    return json.loads(body), response.status
                except json.JSONDecodeError:
                    return {"text": body}, response.status
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise TournamentalOddsError(f"HTTP {exc.code}: {details[:240]}") from exc
        except URLError as exc:
            raise TournamentalOddsError(f"network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TournamentalOddsError("request timed out") from exc

    def _url(self, path: str) -> str:
        base_url = getattr(self.settings, "tournamental_odds_base_url", "https://odds.tournamental.com").rstrip("/")
        safe_path = path if path.startswith("/") else f"/{path}"
        return f"{base_url}{safe_path}"
