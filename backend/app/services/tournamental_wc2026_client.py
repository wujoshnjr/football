from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


class TournamentalWC2026Error(RuntimeError):
    pass


@dataclass(frozen=True)
class TournamentalWC2026Result:
    source_key: str
    configured: bool
    ok: bool
    status_code: int | None
    error: str | None
    record_count: int
    data: Any


class TournamentalWC2026Client:
    def __init__(self, settings, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(getattr(self.settings, "tournamental_wc2026_base_url", None))

    def health(self) -> TournamentalWC2026Result:
        return self._safe_get("health", "/healthz")

    def version(self) -> TournamentalWC2026Result:
        return self._safe_get("version", "/v1/version")

    def upcoming(self) -> TournamentalWC2026Result:
        return self._safe_get("upcoming", "/v1/upcoming")

    def match(self, match_id: str | int) -> TournamentalWC2026Result:
        safe_match_id = quote(str(match_id), safe="")
        return self._safe_get("match", f"/v1/match/{safe_match_id}")

    def _safe_get(self, label: str, path: str) -> TournamentalWC2026Result:
        if not self.configured:
            return TournamentalWC2026Result("tournamental_wc2026", False, False, None, "missing_base_url", 0, None)
        try:
            payload, status_code = self._get_json(path)
            count = len(payload) if isinstance(payload, list) else len(payload.keys()) if isinstance(payload, dict) else 1
            return TournamentalWC2026Result("tournamental_wc2026", True, True, status_code, None, count, payload)
        except TournamentalWC2026Error as exc:
            return TournamentalWC2026Result("tournamental_wc2026", True, False, None, f"{label}: {exc}", 0, None)

    def _get_json(self, path: str) -> tuple[Any, int | None]:
        request = Request(self._url(path), headers={"User-Agent": "football-worldcup-tournamental-wc2026-client/1.0"})
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
            raise TournamentalWC2026Error(f"HTTP {exc.code}: {details[:240]}") from exc
        except URLError as exc:
            raise TournamentalWC2026Error(f"network error: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TournamentalWC2026Error("request timed out") from exc

    def _url(self, path: str) -> str:
        base_url = getattr(self.settings, "tournamental_wc2026_base_url", "https://wc2026.tournamental.com").rstrip("/")
        safe_path = path if path.startswith("/") else f"/{path}"
        return f"{base_url}{safe_path}"
