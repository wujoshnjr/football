from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


class ExternalAPIConfigError(RuntimeError):
    pass


class ExternalAPIRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class APIResult:
    source: str
    ok: bool
    status_code: int | None
    data: dict[str, Any] | list[Any] | None = None
    error: str | None = None


class BaseExternalAPIClient:
    source_key: str = "external"

    def __init__(self, base_url: str | None, timeout_seconds: float = 12.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    async def _get(self, path: str, headers: dict[str, str] | None = None, params: dict[str, Any] | None = None) -> APIResult:
        if not self.configured:
            return APIResult(
                source=self.source_key,
                ok=False,
                status_code=None,
                error="Source is not configured. Check base URL and API key environment variables.",
            )

        url = f"{self.base_url}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(url, headers=headers or {}, params=params or {})
            try:
                data = response.json()
            except ValueError:
                data = {"raw": response.text[:500]}
            return APIResult(
                source=self.source_key,
                ok=200 <= response.status_code < 300,
                status_code=response.status_code,
                data=data,
                error=None if 200 <= response.status_code < 300 else f"HTTP {response.status_code}",
            )
        except httpx.HTTPError as exc:
            return APIResult(
                source=self.source_key,
                ok=False,
                status_code=None,
                error=str(exc),
            )


class FootballDataClient(BaseExternalAPIClient):
    source_key = "football_data"

    def __init__(self, base_url: str | None, token: str | None) -> None:
        super().__init__(base_url)
        self.token = token

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.token)

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise ExternalAPIConfigError("FOOTBALL_DATA_TOKEN is missing.")
        return {"X-Auth-Token": self.token}

    async def get_competition(self, code: str = "WC") -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="FOOTBALL_DATA_TOKEN is missing.")
        return await self._get(f"competitions/{code}", headers=self._headers())

    async def get_worldcup_matches(self, season: int = 2026) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="FOOTBALL_DATA_TOKEN is missing.")
        return await self._get("competitions/WC/matches", headers=self._headers(), params={"season": season})


class APIFootballClient(BaseExternalAPIClient):
    source_key = "api_football"

    def __init__(self, base_url: str | None, key: str | None, auth_mode: str = "apisports", rapidapi_host: str | None = None) -> None:
        super().__init__(base_url)
        self.key = key
        self.auth_mode = auth_mode
        self.rapidapi_host = rapidapi_host

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.key)

    def _headers(self) -> dict[str, str]:
        if not self.key:
            raise ExternalAPIConfigError("API_FOOTBALL_KEY is missing.")
        if self.auth_mode == "rapidapi":
            headers = {"X-RapidAPI-Key": self.key}
            if self.rapidapi_host:
                headers["X-RapidAPI-Host"] = self.rapidapi_host
            return headers
        return {"x-apisports-key": self.key}

    async def get_status(self) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="API_FOOTBALL_KEY is missing.")
        return await self._get("status", headers=self._headers())

    async def get_worldcup_fixtures(self, season: int = 2026) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="API_FOOTBALL_KEY is missing.")
        return await self._get("fixtures", headers=self._headers(), params={"league": 1, "season": season})

    async def get_prediction(self, fixture_id: int) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="API_FOOTBALL_KEY is missing.")
        return await self._get("predictions", headers=self._headers(), params={"fixture": fixture_id})


class ZafronixWorldCupClient(BaseExternalAPIClient):
    source_key = "zafronix_worldcup"

    def __init__(
        self,
        base_url: str | None,
        key: str | None,
        key_header: str = "Authorization",
        key_prefix: str = "Bearer ",
        health_path: str = "health",
    ) -> None:
        super().__init__(base_url)
        self.key = key
        self.key_header = key_header
        self.key_prefix = key_prefix
        self.health_path = health_path

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.key)

    def _headers(self) -> dict[str, str]:
        if not self.key:
            raise ExternalAPIConfigError("ZAFRONIX_WORLDCUP_KEY is missing.")
        value = f"{self.key_prefix}{self.key}" if self.key_header.lower() == "authorization" else self.key
        return {self.key_header: value}

    async def health(self) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="ZAFRONIX_WORLDCUP_KEY or base URL is missing.")
        return await self._get(self.health_path, headers=self._headers())

    async def get_path(self, path: str, params: dict[str, Any] | None = None) -> APIResult:
        if not self.configured:
            return APIResult(self.source_key, False, None, error="ZAFRONIX_WORLDCUP_KEY or base URL is missing.")
        return await self._get(path, headers=self._headers(), params=params)
