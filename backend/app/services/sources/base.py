from __future__ import annotations

import abc
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx


SENSITIVE_QUERY_NAMES = {
    "api_key",
    "apikey",
    "api-key",
    "key",
    "token",
    "access_token",
    "auth_token",
    "subscription-key",
    "ocp-apim-subscription-key",
}


@dataclass(frozen=True)
class SourceAdapterResult:
    """Normalized result returned by every source adapter.

    This is intentionally richer than the legacy FixtureIngestionService result so it can
    power source-health reports, CI artifacts, and future database writes without losing
    important provenance or failure metadata.
    """

    source_key: str
    attempted: bool = False
    configured: bool = False
    enabled: bool = False
    ok: bool = False
    status: str = "unknown"
    status_code: int | None = None
    error: str | None = None
    record_count: int = 0
    records: list[dict[str, Any]] = field(default_factory=list)
    request_url_redacted: str | None = None
    latency_ms: int | None = None
    generated_at: str | None = None
    retryable: bool = False

    def to_report_dict(self, include_records: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_records:
            payload["records"] = []
        return payload


class BaseSourceAdapter(abc.ABC):
    """Base class for all read-only source adapters.

    Rules enforced by this layer:
    - Never place secrets in request_url_redacted.
    - External API failures return SourceAdapterResult instead of raising.
    - Adapters may be used for health checks before they are wired into ingestion.
    """

    source_key = "__undefined__"
    produces_fixtures = False

    def __init__(self, settings: Any, timeout_seconds: int = 12) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    async def fetch(self) -> SourceAdapterResult:
        """Fetch and normalize this source."""

    def setting(self, name: str, default: Any = None) -> Any:
        return getattr(self.settings, name, default)

    def bool_setting(self, name: str, default: bool = False) -> bool:
        return bool(getattr(self.settings, name, default))

    def result(self, **kwargs: Any) -> SourceAdapterResult:
        return SourceAdapterResult(source_key=self.source_key, **kwargs)

    def disabled_result(self, configured: bool = False, status: str = "disabled") -> SourceAdapterResult:
        return self.result(
            attempted=False,
            configured=configured,
            enabled=False,
            ok=False,
            status=status,
            record_count=0,
            records=[],
            retryable=False,
            generated_at=utc_now(),
        )

    def missing_credentials_result(self, configured: bool = False, error: str | None = None) -> SourceAdapterResult:
        return self.result(
            attempted=False,
            configured=configured,
            enabled=False,
            ok=False,
            status="missing_credentials",
            error=error,
            record_count=0,
            records=[],
            retryable=False,
            generated_at=utc_now(),
        )

    def missing_url_result(self, configured: bool = False) -> SourceAdapterResult:
        return self.result(
            attempted=False,
            configured=configured,
            enabled=False,
            ok=False,
            status="missing_url",
            record_count=0,
            records=[],
            retryable=False,
            generated_at=utc_now(),
        )

    def missing_world_cup_ids_result(self, configured: bool = True) -> SourceAdapterResult:
        return self.result(
            attempted=False,
            configured=configured,
            enabled=False,
            ok=False,
            status="missing_world_cup_ids",
            record_count=0,
            records=[],
            retryable=False,
            generated_at=utc_now(),
        )

    def readiness_result(
        self,
        *,
        configured: bool,
        enabled: bool,
        status: str,
        ok: bool | None = None,
        error: str | None = None,
        extra_records: list[dict[str, Any]] | None = None,
    ) -> SourceAdapterResult:
        records = extra_records or []
        return self.result(
            attempted=False,
            configured=configured,
            enabled=enabled,
            ok=enabled if ok is None else ok,
            status=status,
            error=error,
            record_count=len(records),
            records=records,
            retryable=False,
            generated_at=utc_now(),
        )

    async def fetch_json(
        self,
        url: str | None,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        configured: bool = True,
        enabled: bool = True,
    ) -> SourceAdapterResult:
        if not enabled:
            return self.disabled_result(configured=configured)
        if not url:
            return self.missing_url_result(configured=configured)

        request_url = build_url(url, params=params)
        redacted_url = redact_url(request_url)
        started = time.perf_counter()

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(request_url, headers=dict(headers or {}))
            latency_ms = int((time.perf_counter() - started) * 1000)

            if response.status_code != 200:
                return self.http_error_result(response.status_code, redacted_url, latency_ms)

            try:
                payload = response.json()
            except ValueError as exc:
                return self.result(
                    attempted=True,
                    configured=configured,
                    enabled=enabled,
                    ok=False,
                    status="parse_error",
                    status_code=response.status_code,
                    error=f"json_decode_error: {exc}",
                    record_count=0,
                    records=[],
                    request_url_redacted=redacted_url,
                    latency_ms=latency_ms,
                    retryable=False,
                    generated_at=utc_now(),
                )

            try:
                records = self.extract_records(payload)
            except (TypeError, ValueError, KeyError) as exc:
                return self.result(
                    attempted=True,
                    configured=configured,
                    enabled=enabled,
                    ok=False,
                    status="schema_mismatch",
                    status_code=response.status_code,
                    error=str(exc),
                    record_count=0,
                    records=[],
                    request_url_redacted=redacted_url,
                    latency_ms=latency_ms,
                    retryable=False,
                    generated_at=utc_now(),
                )

            if not records:
                return self.result(
                    attempted=True,
                    configured=configured,
                    enabled=enabled,
                    ok=False,
                    status="empty_response",
                    status_code=response.status_code,
                    record_count=0,
                    records=[],
                    request_url_redacted=redacted_url,
                    latency_ms=latency_ms,
                    retryable=False,
                    generated_at=utc_now(),
                )

            return self.result(
                attempted=True,
                configured=configured,
                enabled=enabled,
                ok=True,
                status="ok",
                status_code=response.status_code,
                record_count=len(records),
                records=records,
                request_url_redacted=redacted_url,
                latency_ms=latency_ms,
                retryable=False,
                generated_at=utc_now(),
            )
        except httpx.TimeoutException as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return self.result(
                attempted=True,
                configured=configured,
                enabled=enabled,
                ok=False,
                status="timeout",
                error=str(exc) or "timeout",
                record_count=0,
                records=[],
                request_url_redacted=redacted_url,
                latency_ms=latency_ms,
                retryable=True,
                generated_at=utc_now(),
            )
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return self.result(
                attempted=True,
                configured=configured,
                enabled=enabled,
                ok=False,
                status="upstream_error",
                error=str(exc),
                record_count=0,
                records=[],
                request_url_redacted=redacted_url,
                latency_ms=latency_ms,
                retryable=True,
                generated_at=utc_now(),
            )

    def http_error_result(self, status_code: int, request_url_redacted: str, latency_ms: int | None) -> SourceAdapterResult:
        if status_code in {401, 403}:
            status = "unauthorized_or_forbidden"
            retryable = False
        elif status_code == 429:
            status = "rate_limited"
            retryable = True
        elif status_code >= 500:
            status = "upstream_error"
            retryable = True
        else:
            status = "upstream_error"
            retryable = False
        return self.result(
            attempted=True,
            configured=True,
            enabled=True,
            ok=False,
            status=status,
            status_code=status_code,
            record_count=0,
            records=[],
            request_url_redacted=request_url_redacted,
            latency_ms=latency_ms,
            retryable=retryable,
            generated_at=utc_now(),
        )

    def extract_records(self, payload: Any) -> list[dict[str, Any]]:
        """Default record extraction for health checks.

        Specific adapters should override this when their payload shape is known.
        """
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("response", "matches", "events", "games", "data", "results", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        query.append((key, "REDACTED" if key.lower() in SENSITIVE_QUERY_NAMES else value))
    redacted = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    redacted = re.sub(r"tnm_[A-Za-z0-9_\-]+", "tnm_REDACTED", redacted)
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9_\.\-]+", r"\1REDACTED", redacted, flags=re.IGNORECASE)
    return redacted


def build_url(base_or_url: str, path: str | None = None, params: Mapping[str, Any] | None = None) -> str:
    base = str(base_or_url or "").rstrip("/")
    url = base if not path else f"{base}/{str(path).lstrip('/')}"
    if not params:
        return url
    filtered = {key: value for key, value in params.items() if value is not None}
    if not filtered:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(filtered)}"
