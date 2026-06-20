from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

REQUIRED_ENDPOINTS: tuple[str, ...] = (
    "/health",
    "/data-sources",
    "/data-sources/canonical",
    "/ingestion/fixtures",
    "/fixtures",
)

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

SECRET_NAME_HINTS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH")

UrlOpener = Callable[..., Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_base_url(value: str) -> str:
    return value.strip().rstrip("/")


def redact_url(url: str) -> str:
    parts = urlsplit(url)
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        redacted_value = "REDACTED" if key.lower() in SENSITIVE_QUERY_NAMES else value
        query.append((key, redacted_value))
    redacted = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    redacted = re.sub(r"(Bearer\s+)[A-Za-z0-9_.\-]+", r"\1REDACTED", redacted, flags=re.IGNORECASE)
    return redacted


def redact_text(text: str | None, environ: dict[str, str] | None = None) -> str | None:
    if text is None:
        return None
    redacted = redact_url(str(text))
    env = environ if environ is not None else dict(os.environ)
    for name, value in env.items():
        if not value or len(value) < 4:
            continue
        if any(hint in name.upper() for hint in SECRET_NAME_HINTS):
            redacted = redacted.replace(value, "REDACTED")
    redacted = re.sub(r"(api[_-]?key=)[^\s&]+", r"\1REDACTED", redacted, flags=re.IGNORECASE)
    redacted = re.sub(r"(token=)[^\s&]+", r"\1REDACTED", redacted, flags=re.IGNORECASE)
    return redacted


def endpoint_url(base_url: str, endpoint: str) -> str:
    return f"{normalize_base_url(base_url)}{endpoint}"


def endpoint_result(
    endpoint: str,
    *,
    attempted: bool,
    success: bool,
    status_code: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "attempted": attempted,
        "success": success,
        "status_code": status_code,
        "error": error,
    }


def check_endpoint(
    base_url: str,
    endpoint: str,
    *,
    opener: UrlOpener = urlopen,
    timeout: int = 10,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    url = endpoint_url(base_url, endpoint)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "football-runtime-smoke-check"})
    response = None
    try:
        response = opener(request, timeout=timeout)
        status_code = int(getattr(response, "status", response.getcode()))
        raw_body = response.read()
        if isinstance(raw_body, bytes):
            body_text = raw_body.decode("utf-8")
        else:
            body_text = str(raw_body)
        json.loads(body_text)
        return endpoint_result(endpoint, attempted=True, success=200 <= status_code < 300, status_code=status_code)
    except HTTPError as exc:
        return endpoint_result(
            endpoint,
            attempted=True,
            success=False,
            status_code=int(exc.code),
            error=redact_text(f"http_error: {exc.reason}", environ=environ),
        )
    except URLError as exc:
        return endpoint_result(
            endpoint,
            attempted=True,
            success=False,
            status_code=None,
            error=redact_text(f"url_error: {exc.reason}", environ=environ),
        )
    except TimeoutError as exc:
        return endpoint_result(
            endpoint,
            attempted=True,
            success=False,
            status_code=None,
            error=redact_text(f"timeout: {exc}", environ=environ),
        )
    except json.JSONDecodeError as exc:
        return endpoint_result(
            endpoint,
            attempted=True,
            success=False,
            status_code=None,
            error=redact_text(f"invalid_json: {exc}", environ=environ),
        )
    except Exception as exc:  # noqa: BLE001 - smoke check must report instead of crashing
        return endpoint_result(
            endpoint,
            attempted=True,
            success=False,
            status_code=None,
            error=redact_text(f"unexpected_error: {type(exc).__name__}: {exc}", environ=environ),
        )
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()


def missing_backend_url_report() -> dict[str, Any]:
    return {
        "report_type": "runtime_smoke_check",
        "generated_at": utc_now(),
        "status": "missing_backend_url",
        "backend_url": None,
        "endpoints": [
            endpoint_result(endpoint, attempted=False, success=False, error="FOOTBALL_BACKEND_URL is not set")
            for endpoint in REQUIRED_ENDPOINTS
        ],
        "safety": locked_safety_flags(),
    }


def locked_safety_flags() -> dict[str, bool]:
    return {
        "live_betting_allowed": False,
        "automated_wagering_allowed": False,
        "real_money_betting_allowed": False,
        "pick_submission_allowed": False,
    }


def build_report(
    backend_url: str | None = None,
    *,
    opener: UrlOpener = urlopen,
    timeout: int = 10,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    env = environ if environ is not None else dict(os.environ)
    base_url = backend_url if backend_url is not None else env.get("FOOTBALL_BACKEND_URL")
    if not base_url or not base_url.strip():
        return missing_backend_url_report()

    normalized_url = normalize_base_url(base_url)
    results = [
        check_endpoint(normalized_url, endpoint, opener=opener, timeout=timeout, environ=env)
        for endpoint in REQUIRED_ENDPOINTS
    ]
    success = all(result["success"] for result in results)
    return {
        "report_type": "runtime_smoke_check",
        "generated_at": utc_now(),
        "status": "ok" if success else "failed",
        "backend_url": redact_url(normalized_url),
        "endpoints": results,
        "safety": locked_safety_flags(),
    }


def main() -> int:
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
