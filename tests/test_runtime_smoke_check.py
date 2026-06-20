from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import runtime_smoke_check


class FakeResponse:
    def __init__(self, status: int = 200, body: str = "{}") -> None:
        self.status = status
        self._body = body.encode("utf-8")
        self.closed = False

    def getcode(self) -> int:
        return self.status

    def read(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


def test_required_endpoints_are_exact() -> None:
    assert runtime_smoke_check.REQUIRED_ENDPOINTS == (
        "/health",
        "/data-sources",
        "/data-sources/canonical",
        "/ingestion/fixtures",
        "/fixtures",
    )


def test_missing_backend_url_does_not_crash(monkeypatch) -> None:
    monkeypatch.delenv("FOOTBALL_BACKEND_URL", raising=False)

    report = runtime_smoke_check.build_report(environ={})

    assert report["status"] == "missing_backend_url"
    assert report["backend_url"] is None
    assert len(report["endpoints"]) == len(runtime_smoke_check.REQUIRED_ENDPOINTS)
    assert all(item["attempted"] is False for item in report["endpoints"])
    assert all(item["success"] is False for item in report["endpoints"])


def test_mock_endpoint_success_generates_ok_report() -> None:
    requested_paths: list[str] = []

    def fake_opener(request, timeout: int = 10):
        requested_paths.append(request.full_url)
        return FakeResponse(200, '{"ok": true}')

    report = runtime_smoke_check.build_report(
        "https://backend.example.test",
        opener=fake_opener,
        environ={},
    )

    assert report["status"] == "ok"
    assert report["backend_url"] == "https://backend.example.test"
    assert [item["endpoint"] for item in report["endpoints"]] == list(runtime_smoke_check.REQUIRED_ENDPOINTS)
    assert all(item["attempted"] is True for item in report["endpoints"])
    assert all(item["success"] is True for item in report["endpoints"])
    assert all(item["status_code"] == 200 for item in report["endpoints"])
    assert requested_paths == [f"https://backend.example.test{endpoint}" for endpoint in runtime_smoke_check.REQUIRED_ENDPOINTS]


def test_mock_endpoint_failure_does_not_crash() -> None:
    def fake_opener(request, timeout: int = 10):
        if request.full_url.endswith("/health"):
            return FakeResponse(200, '{"status": "ok"}')
        raise URLError("provider unavailable")

    report = runtime_smoke_check.build_report(
        "https://backend.example.test",
        opener=fake_opener,
        environ={},
    )

    assert report["status"] == "failed"
    assert report["endpoints"][0]["success"] is True
    assert any(item["success"] is False for item in report["endpoints"])
    assert all("provider unavailable" in (item["error"] or "") or item["success"] for item in report["endpoints"])


def test_report_redacts_api_key_values() -> None:
    secret = "secret-runtime-api-key"

    def fake_opener(request, timeout: int = 10):
        raise RuntimeError(f"failed with {secret} at {request.full_url}")

    report = runtime_smoke_check.build_report(
        f"https://backend.example.test?api_key={secret}",
        opener=fake_opener,
        environ={"SOME_API_KEY": secret, "FOOTBALL_BACKEND_URL": f"https://backend.example.test?api_key={secret}"},
    )

    serialized = json.dumps(report, sort_keys=True)
    assert secret not in serialized
    assert "api_key=REDACTED" in serialized
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


def test_invalid_json_marks_endpoint_failed() -> None:
    def fake_opener(request, timeout: int = 10):
        return FakeResponse(200, "not json")

    report = runtime_smoke_check.build_report(
        "https://backend.example.test",
        opener=fake_opener,
        environ={},
    )

    assert report["status"] == "failed"
    assert all(item["attempted"] is True for item in report["endpoints"])
    assert all(item["success"] is False for item in report["endpoints"])
    assert all((item["error"] or "").startswith("invalid_json") for item in report["endpoints"])
