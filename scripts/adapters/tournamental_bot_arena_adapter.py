from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from scripts.source_registry import get_source_status
from scripts.source_report_schema import build_source_report


SOURCE_KEY = "tournamental_bot_arena"
FORBIDDEN_OUTPUT_KEYS = {"recommended_bet", "stake_size"}
ALLOWED_SIGNAL_ROLES = ("market_consensus", "external_signal", "paper_tracking")

HttpGet = Callable[[str, Mapping[str, str], Mapping[str, Any], float], Any]


class AdapterHTTPError(RuntimeError):
    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(message or f"HTTP {status_code}")
        self.status_code = int(status_code)
        self.message = message or f"HTTP {status_code}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): sanitize_payload(child)
            for key, child in value.items()
            if str(key) not in FORBIDDEN_OUTPUT_KEYS
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


def http_status_to_source_status(status_code: int) -> str:
    if status_code in {401, 403}:
        return "unauthorized_or_forbidden"
    if status_code == 429:
        return "rate_limited"
    if status_code >= 500:
        return "upstream_error"
    return "upstream_error"


class TournamentalBotArenaAdapter:
    """Read-only Tournamental Bot Arena adapter.

    This adapter deliberately exposes only catalogue, odds, injury, weather, and
    health-read methods. It does not implement pick submission methods.
    """

    def __init__(
        self,
        environ: Mapping[str, str] | None = None,
        http_get: HttpGet | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.environ = environ if environ is not None else os.environ
        self.http_get = http_get or self._urllib_get
        self.timeout_seconds = float(timeout_seconds)

    @property
    def base_url(self) -> str:
        return str(self.environ.get("TOURNAMENTAL_BASE_URL") or "").rstrip("/")

    @property
    def api_key(self) -> str:
        return str(self.environ.get("TOURNAMENTAL_API_KEY") or "")

    @property
    def tournament_id(self) -> str:
        return str(self.environ.get("TOURNAMENTAL_TOURNAMENT_ID") or "fifa-wc-2026")

    @property
    def enabled(self) -> bool:
        return bool_value(self.environ.get("TOURNAMENTAL_ENABLED"), False)

    @property
    def read_only_feeds_enabled(self) -> bool:
        return bool_value(self.environ.get("TOURNAMENTAL_ENABLE_READ_ONLY_FEEDS"), True)

    @property
    def pick_submission_requested(self) -> bool:
        return bool_value(self.environ.get("TOURNAMENTAL_ENABLE_PICK_SUBMISSION"), False)

    @property
    def pick_submission_allowed(self) -> bool:
        return False

    def safety_payload(self) -> dict[str, Any]:
        return {
            "read_only_only": True,
            "pick_submission_requested": self.pick_submission_requested,
            "pick_submission_allowed": False,
            "pick_submission_locked": True,
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
        }

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.pick_submission_requested:
            warnings.append("TOURNAMENTAL_ENABLE_PICK_SUBMISSION is ignored because pick submission is locked false.")
        return warnings

    def configuration_status(self) -> tuple[str, list[str]]:
        missing: list[str] = []
        if not self.enabled:
            return "disabled", missing
        if not self.read_only_feeds_enabled:
            return "disabled", missing
        if not self.base_url:
            missing.append("TOURNAMENTAL_BASE_URL")
        if not self.api_key:
            missing.append("TOURNAMENTAL_API_KEY")
        if not self.tournament_id:
            missing.append("TOURNAMENTAL_TOURNAMENT_ID")
        if missing:
            if "TOURNAMENTAL_TOURNAMENT_ID" in missing and len(missing) == 1:
                return "missing_world_cup_ids", missing
            return "missing_credentials", missing
        return "ok", missing

    def source_report(
        self,
        *,
        attempted: bool,
        status: str,
        record_count: int = 0,
        error: str | None = None,
        missing_env: list[str] | None = None,
    ) -> dict[str, Any]:
        source = get_source_status(SOURCE_KEY, self.environ)
        return build_source_report(
            source,
            attempted=attempted,
            success=status == "ok",
            status=status,
            record_count=record_count,
            error=error,
            missing_env=missing_env if missing_env is not None else source.get("missing_env", []),
            checked_at=utc_now(),
        )

    def health_check(self) -> dict[str, Any]:
        status, missing = self.configuration_status()
        return self._empty_report(
            data_type="health_check",
            endpoint="configuration",
            status=status,
            attempted=False,
            missing_env=missing,
        )

    def get_match_catalogue(self) -> dict[str, Any]:
        endpoint = f"/tournaments/{urllib.parse.quote(self.tournament_id)}/matches"
        return self._read_only_endpoint("match_catalogue", endpoint, record_keys=("matches", "fixtures", "data", "results"))

    def get_odds(self, match_id: str | None = None) -> dict[str, Any]:
        params = {"match_id": match_id} if match_id else {}
        endpoint = f"/tournaments/{urllib.parse.quote(self.tournament_id)}/odds"
        return self._read_only_endpoint("odds", endpoint, params=params, record_keys=("odds", "markets", "data", "results"))

    def get_injuries(self, match_id: str | None = None) -> dict[str, Any]:
        params = {"match_id": match_id} if match_id else {}
        endpoint = f"/tournaments/{urllib.parse.quote(self.tournament_id)}/injuries"
        return self._read_only_endpoint("injuries", endpoint, params=params, record_keys=("injuries", "players", "data", "results"))

    def get_weather(self, match_id: str | None = None) -> dict[str, Any]:
        params = {"match_id": match_id} if match_id else {}
        endpoint = f"/tournaments/{urllib.parse.quote(self.tournament_id)}/weather"
        return self._read_only_endpoint("weather", endpoint, params=params, record_keys=("weather", "conditions", "data", "results"))

    def _read_only_endpoint(
        self,
        data_type: str,
        endpoint: str,
        params: Mapping[str, Any] | None = None,
        record_keys: tuple[str, ...] = ("data", "results"),
    ) -> dict[str, Any]:
        config_status, missing = self.configuration_status()
        if config_status != "ok":
            return self._empty_report(data_type=data_type, endpoint=endpoint, status=config_status, attempted=False, missing_env=missing)

        payload, status, error = self._request_json(endpoint, params or {})
        if status != "ok":
            return self._empty_report(data_type=data_type, endpoint=endpoint, status=status, attempted=True, error=error)

        records = self._extract_records(payload, record_keys)
        if records is None:
            return self._empty_report(data_type=data_type, endpoint=endpoint, status="schema_mismatch", attempted=True, error="record_list_missing")
        if not records:
            return self._empty_report(data_type=data_type, endpoint=endpoint, status="empty_response", attempted=True)

        enriched = [self._enrich_record(record, data_type=data_type, endpoint=endpoint) for record in records]
        return self._records_report(data_type=data_type, endpoint=endpoint, records=enriched)

    def _request_json(self, endpoint: str, params: Mapping[str, Any]) -> tuple[Any, str, str | None]:
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "football-prediction-read-only-tournamental-adapter",
        }
        try:
            response = self.http_get(url, headers, params, self.timeout_seconds)
            payload = self._decode_response(response)
        except AdapterHTTPError as exc:
            return None, http_status_to_source_status(exc.status_code), exc.message
        except (TimeoutError, socket.timeout):
            return None, "timeout", "timeout"
        except json.JSONDecodeError as exc:
            return None, "schema_mismatch", str(exc)
        except Exception as exc:  # noqa: BLE001 - adapter reports upstream errors instead of crashing
            return None, "upstream_error", type(exc).__name__

        if payload in (None, ""):
            return None, "empty_response", None
        return sanitize_payload(payload), "ok", None

    def _decode_response(self, response: Any) -> Any:
        if hasattr(response, "json"):
            return response.json()
        if isinstance(response, bytes):
            return json.loads(response.decode("utf-8"))
        if isinstance(response, str):
            return json.loads(response)
        return response

    def _urllib_get(self, url: str, headers: Mapping[str, str], params: Mapping[str, Any], timeout: float) -> Any:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value is not None})
        full_url = f"{url}?{query}" if query else url
        request = urllib.request.Request(full_url, headers=dict(headers), method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured read-only endpoint
                return response.read()
        except urllib.error.HTTPError as exc:
            raise AdapterHTTPError(exc.code, str(exc)) from exc

    def _extract_records(self, payload: Any, record_keys: tuple[str, ...]) -> list[Any] | None:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return None
        for key in record_keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict) and isinstance(value.get("items"), list):
                return value["items"]
        return None

    def _enrich_record(self, record: Any, *, data_type: str, endpoint: str) -> dict[str, Any]:
        sanitized = sanitize_payload(record)
        payload = dict(sanitized) if isinstance(sanitized, dict) else {"value": sanitized}
        role = "market_consensus" if data_type == "odds" else "external_signal"
        if data_type == "odds":
            payload["signal_role"] = role
            payload["allowed_signal_roles"] = list(ALLOWED_SIGNAL_ROLES)
        payload["source_provenance"] = [
            {
                "source": SOURCE_KEY,
                "data_type": data_type,
                "endpoint": endpoint,
                "fetched_at": utc_now(),
                "role": role,
                "official": False,
                "read_only": True,
            }
        ]
        return payload

    def _records_report(self, *, data_type: str, endpoint: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "report_type": "tournamental_bot_arena_read_only_report",
            "source": SOURCE_KEY,
            "data_type": data_type,
            "endpoint": endpoint,
            "checked_at": utc_now(),
            "records": records,
            "record_count": len(records),
            "signal_roles": list(ALLOWED_SIGNAL_ROLES),
            "source_report": self.source_report(attempted=True, status="ok", record_count=len(records)),
            "safety": self.safety_payload(),
            "warnings": self.warnings(),
        }

    def _empty_report(
        self,
        *,
        data_type: str,
        endpoint: str,
        status: str,
        attempted: bool,
        error: str | None = None,
        missing_env: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "report_type": "tournamental_bot_arena_read_only_report",
            "source": SOURCE_KEY,
            "data_type": data_type,
            "endpoint": endpoint,
            "checked_at": utc_now(),
            "records": [],
            "record_count": 0,
            "signal_roles": list(ALLOWED_SIGNAL_ROLES),
            "source_report": self.source_report(
                attempted=attempted,
                status=status,
                record_count=0,
                error=error,
                missing_env=missing_env,
            ),
            "safety": self.safety_payload(),
            "warnings": self.warnings(),
        }
