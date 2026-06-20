from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.source_registry import CANONICAL_SOURCE_KEYS, get_source_status, list_sources
from scripts.source_report_schema import (
    REQUIRED_SOURCE_REPORT_FIELDS,
    SUPPORTED_SOURCE_STATUSES,
    build_source_report,
    validate_source_report,
)


EXPECTED_SOURCE_KEYS = (
    "football_data",
    "api_football",
    "worldcup_2026_api",
    "openfootball_worldcup_json",
    "zafronix_worldcup",
    "thesportsdb_worldcup",
    "statsbomb_open_data",
    "open_meteo_weather",
    "gdelt_news",
    "fifa_ranking_source",
    "sportsdataio_worldcup",
    "thestatsapi_worldcup",
    "tournamental_bot_arena",
)


def test_registry_contains_exactly_the_13_canonical_sources() -> None:
    sources = list_sources({})
    keys = tuple(source["key"] for source in sources)

    assert CANONICAL_SOURCE_KEYS == EXPECTED_SOURCE_KEYS
    assert keys == EXPECTED_SOURCE_KEYS
    assert len(keys) == 13
    assert len(set(keys)) == 13


def test_each_source_has_required_public_metadata() -> None:
    required_fields = {
        "key",
        "name",
        "requires_key",
        "official",
        "role",
        "production_use",
        "priority",
        "env_vars",
        "enabled_env",
        "enabled",
        "configured",
        "missing_env",
        "missing_reason",
    }

    for source in list_sources({}):
        assert required_fields.issubset(source)
        assert isinstance(source["env_vars"], list)
        assert isinstance(source["missing_env"], list)
        assert isinstance(source["enabled"], bool)
        assert isinstance(source["configured"], bool)
        assert isinstance(source["priority"], int)


def test_missing_env_does_not_crash_and_reports_missing_reason() -> None:
    source = get_source_status("football_data", {})

    assert source["enabled"] is True
    assert source["configured"] is False
    assert source["missing_env"] == ["FOOTBALL_DATA_TOKEN"]
    assert source["missing_reason"] == "missing_env: FOOTBALL_DATA_TOKEN"


def test_public_defaults_configure_no_key_static_sources() -> None:
    openfootball = get_source_status("openfootball_worldcup_json", {})
    statsbomb = get_source_status("statsbomb_open_data", {})

    assert openfootball["enabled"] is True
    assert openfootball["configured"] is True
    assert openfootball["missing_reason"] is None
    assert statsbomb["enabled"] is True
    assert statsbomb["configured"] is True


def test_confirmed_world_cup_ids_are_available_without_secrets() -> None:
    sportsdataio = get_source_status("sportsdataio_worldcup", {})
    thestatsapi = get_source_status("thestatsapi_worldcup", {})

    assert sportsdataio["world_cup_ids"] == {
        "competition_key": "21",
        "competition_id": "21",
        "season_id": "368",
        "season": "2026",
    }
    assert thestatsapi["world_cup_ids"] == {
        "competition_id": "comp_6107",
        "season_id": "sn_118868",
    }


def test_configured_sources_do_not_echo_secret_values() -> None:
    env = {
        "SPORTSDATAIO_API_KEY": "secret-sportsdataio-key",
        "SPORTSDATAIO_ENABLED": "true",
        "THESTATSAPI_KEY": "secret-thestatsapi-key",
        "THESTATSAPI_ENABLED": "true",
    }

    sportsdataio = get_source_status("sportsdataio_worldcup", env)
    thestatsapi = get_source_status("thestatsapi_worldcup", env)

    assert sportsdataio["enabled"] is True
    assert sportsdataio["configured"] is True
    assert sportsdataio["missing_env"] == []
    assert thestatsapi["enabled"] is True
    assert thestatsapi["configured"] is True
    assert "secret-sportsdataio-key" not in str(sportsdataio)
    assert "secret-thestatsapi-key" not in str(thestatsapi)


def test_tournamental_pick_submission_is_effectively_locked_false() -> None:
    env = {
        "TOURNAMENTAL_ENABLED": "true",
        "TOURNAMENTAL_BASE_URL": "https://example.test/tournamental",
        "TOURNAMENTAL_API_KEY": "secret-tournamental-key",
        "TOURNAMENTAL_ENABLE_PICK_SUBMISSION": "true",
    }

    source = get_source_status("tournamental_bot_arena", env)

    assert source["enabled"] is True
    assert source["configured"] is True
    assert source["safety_flags"]["pick_submission_requested"] is True
    assert source["safety_flags"]["pick_submission_effective"] is False
    assert source["safety_flags"]["pick_submission_locked"] is True
    assert source["safety_flags"]["read_only_only"] is True
    assert source["warnings"] == [
        "TOURNAMENTAL_ENABLE_PICK_SUBMISSION is ignored because pick submission is locked false."
    ]
    assert "secret-tournamental-key" not in str(source)


def test_source_report_schema_accepts_registry_source() -> None:
    source = get_source_status("openfootball_worldcup_json", {})
    report = build_source_report(source, attempted=False, record_count=0)

    assert set(REQUIRED_SOURCE_REPORT_FIELDS).issubset(report)
    assert report["source"]["key"] == "openfootball_worldcup_json"
    assert report["success"] is True
    assert report["status"] == "ok"
    assert report["missing_env"] == []
    validate_source_report(report)


def test_supported_statuses_include_required_failure_modes() -> None:
    assert set(SUPPORTED_SOURCE_STATUSES) == {
        "ok",
        "disabled",
        "missing_credentials",
        "missing_world_cup_ids",
        "missing_world_cup_competition_key",
        "unauthorized_or_forbidden",
        "rate_limited",
        "upstream_error",
        "empty_response",
        "schema_mismatch",
        "timeout",
    }


def test_source_report_schema_rejects_unsupported_status() -> None:
    source = get_source_status("openfootball_worldcup_json", {})

    with pytest.raises(ValueError, match="unsupported source status"):
        build_source_report(source, status="bad_status")


def test_source_report_schema_rejects_negative_record_count() -> None:
    source = get_source_status("openfootball_worldcup_json", {})

    with pytest.raises(ValueError, match="record_count"):
        build_source_report(source, record_count=-1)
