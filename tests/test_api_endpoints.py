from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import main
from scripts.source_registry import CANONICAL_SOURCE_KEYS
from scripts.source_report_schema import validate_source_report

client = TestClient(main.app)


def assert_no_forbidden_betting_keys(payload: Any) -> None:
    serialized = json.dumps(payload)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized


def test_health_endpoint_returns_model_version() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "model_version" in payload
    assert_no_forbidden_betting_keys(payload)


def test_runtime_version_endpoint_returns_deploy_metadata_without_secret_leak(monkeypatch) -> None:
    monkeypatch.setenv("GIT_COMMIT", "abc123")
    monkeypatch.setenv("GIT_BRANCH", "main")
    monkeypatch.setenv("DEPLOYED_AT", "2026-06-20T00:00:00Z")
    monkeypatch.setenv("FOOTBALL_DATA_TOKEN", "runtime-secret-token")
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "runtime-secret-sportsdataio")

    response = client.get("/runtime/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["app"] == main.settings.app_name
    assert payload["environment"] == main.settings.app_env
    assert payload["git_commit"] == "abc123"
    assert payload["branch"] == "main"
    assert payload["deployed_at"] == "2026-06-20T00:00:00Z"
    assert payload["live_betting_allowed"] is False
    assert payload["automated_wagering_allowed"] is False
    assert payload["real_money_betting_allowed"] is False
    assert payload["tournamental_pick_submission_allowed"] is False
    serialized = json.dumps(payload)
    assert "runtime-secret-token" not in serialized
    assert "runtime-secret-sportsdataio" not in serialized
    assert_no_forbidden_betting_keys(payload)


def test_runtime_version_endpoint_falls_back_to_unknown(monkeypatch) -> None:
    for key in (
        "GIT_COMMIT",
        "RENDER_GIT_COMMIT",
        "VERCEL_GIT_COMMIT_SHA",
        "GIT_BRANCH",
        "RENDER_GIT_BRANCH",
        "DEPLOYED_AT",
    ):
        monkeypatch.delenv(key, raising=False)

    response = client.get("/runtime/version")

    assert response.status_code == 200
    payload = response.json()
    assert payload["git_commit"] == "unknown"
    assert payload["branch"] == "unknown"
    assert payload["deployed_at"] == "unknown"
    assert payload["live_betting_allowed"] is False
    assert payload["automated_wagering_allowed"] is False
    assert payload["real_money_betting_allowed"] is False
    assert payload["tournamental_pick_submission_allowed"] is False
    assert_no_forbidden_betting_keys(payload)


def test_invalid_fixture_source_uses_standard_error() -> None:
    response = client.get("/fixtures", params={"source": "bad"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "invalid_fixture_source"
    assert payload["detail"]["error"]["details"] == {"source": "bad"}
    assert_no_forbidden_betting_keys(payload)


def test_fixture_not_found_uses_standard_error() -> None:
    response = client.get("/fixtures/missing-fixture", params={"source": "demo"})

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "fixture_not_found"
    assert payload["detail"]["error"]["details"]["fixture_id"] == "missing-fixture"
    assert_no_forbidden_betting_keys(payload)


def test_finished_fixture_prediction_uses_standard_error() -> None:
    response = client.get("/predictions/arg-alg-2026-final", params={"source": "demo"})

    assert response.status_code == 409
    payload = response.json()
    assert payload["detail"]["error"]["code"] == "fixture_finished"
    assert_no_forbidden_betting_keys(payload)


def test_data_sources_endpoint_uses_canonical_13_source_registry() -> None:
    response = client.get("/data-sources")

    assert response.status_code == 200
    payload = response.json()
    assert tuple(source["key"] for source in payload) == CANONICAL_SOURCE_KEYS
    assert len(payload) == 13
    assert len({source["key"] for source in payload}) == 13
    assert all("category" in source for source in payload)
    assert all("reliability" in source for source in payload)
    assert all("notes" in source for source in payload)
    serialized = json.dumps(payload)
    assert "secret-" not in serialized
    assert "tnm_" not in serialized
    assert_no_forbidden_betting_keys(payload)


def test_data_sources_canonical_endpoint_does_not_expose_secret_values() -> None:
    response = client.get("/data-sources/canonical")

    assert response.status_code == 200
    payload = response.json()
    assert tuple(source["key"] for source in payload) == CANONICAL_SOURCE_KEYS
    serialized = json.dumps(payload)
    assert "secret-" not in serialized
    assert "tnm_" not in serialized
    assert_no_forbidden_betting_keys(payload)


def test_ingestion_endpoint_returns_json_report_when_service_fails(monkeypatch) -> None:
    def fail_ingestion() -> dict:
        raise RuntimeError("provider URL with possible secret should not be returned")

    monkeypatch.setattr(main, "fixture_ingestion", fail_ingestion)

    response = client.get("/ingestion/fixtures")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixture_count"] == 0
    assert payload["source_reports"] == []
    assert payload["fixtures"] == []
    assert payload["errors"][0]["error"]["code"] == "fixture_ingestion_failed"
    assert payload["errors"][0]["error"]["details"] == {"error_type": "RuntimeError"}
    assert "possible secret" not in json.dumps(payload)
    assert payload["safety"] == {
        "live_betting_allowed": False,
        "automated_wagering_allowed": False,
        "real_money_betting_allowed": False,
        "pick_submission_allowed": False,
    }
    assert_no_forbidden_betting_keys(payload)


def test_ingestion_endpoint_converts_legacy_sources_to_source_reports(monkeypatch) -> None:
    source_report = {
        "source_key": "football_data",
        "attempted": True,
        "configured": True,
        "enabled": True,
        "ok": False,
        "status": "adapter_exception",
        "error": "upstream failed",
        "record_count": 0,
    }

    monkeypatch.setattr(
        main,
        "fixture_ingestion",
        lambda: {
            "generated_at": "2026-06-20T00:00:00+00:00",
            "fixture_count": 0,
            "sources": [source_report],
            "fixtures": [],
        },
    )

    response = client.get("/ingestion/fixtures")

    assert response.status_code == 200
    payload = response.json()
    assert payload["sources"] == [source_report]
    assert len(payload["source_reports"]) == 1
    assert payload["source_reports"][0]["source"]["key"] == "football_data"
    assert payload["source_reports"][0]["status"] == "upstream_error"
    assert payload["source_reports"][0]["success"] is False
    validate_source_report(payload["source_reports"][0])
    assert payload["errors"] == []
    assert payload["warnings"] == []
    assert payload["safety"]["live_betting_allowed"] is False
    assert_no_forbidden_betting_keys(payload)


def test_ingestion_endpoint_validates_existing_source_reports(monkeypatch) -> None:
    existing_report = {
        "source": {"key": "openfootball_worldcup_json"},
        "attempted": False,
        "success": True,
        "status": "ok",
        "record_count": 0,
        "error": None,
        "missing_env": [],
        "checked_at": "2026-06-20T00:00:00+00:00",
    }

    monkeypatch.setattr(
        main,
        "fixture_ingestion",
        lambda: {
            "generated_at": "2026-06-20T00:00:00+00:00",
            "fixture_count": 0,
            "source_reports": [existing_report],
            "fixtures": [],
        },
    )

    response = client.get("/ingestion/fixtures")

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_reports"] == [existing_report]
    validate_source_report(payload["source_reports"][0])
    assert_no_forbidden_betting_keys(payload)


def test_data_sources_context_endpoint_does_not_crash() -> None:
    response = client.get("/data-sources/context")

    assert response.status_code == 200
    payload = response.json()
    assert "sources_used" in payload
    assert "sources_configured" in payload
    assert "sources_missing" in payload
    assert_no_forbidden_betting_keys(payload)
