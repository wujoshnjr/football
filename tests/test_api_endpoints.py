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

from app import main

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


def test_ingestion_endpoint_adds_source_report_alias_and_safety(monkeypatch) -> None:
    source_report = {"source_key": "football_data", "status": "missing_credentials", "record_count": 0}

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
    assert payload["source_reports"] == [source_report]
    assert payload["errors"] == []
    assert payload["warnings"] == []
    assert payload["safety"]["live_betting_allowed"] is False
    assert_no_forbidden_betting_keys(payload)


def test_data_sources_context_endpoint_does_not_crash() -> None:
    response = client.get("/data-sources/context")

    assert response.status_code == 200
    payload = response.json()
    assert "sources_used" in payload
    assert "sources_configured" in payload
    assert "sources_missing" in payload
    assert_no_forbidden_betting_keys(payload)
