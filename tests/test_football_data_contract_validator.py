from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_data_contract_validator import validate_data_contract, write_data_contract_report
from scripts.source_registry import get_source_status
from scripts.source_report_schema import build_source_report


def write_json(path: Path, payload: dict, *, allow_nan: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, allow_nan=allow_nan), encoding="utf-8")


def valid_source_report() -> dict:
    source = get_source_status("openfootball_worldcup_json", {})
    return build_source_report(source, attempted=True, success=True, status="ok", record_count=1)


def valid_fixture_ingestion_report() -> dict:
    return {
        "run_id": "run-1",
        "checked_at": "2026-06-20T00:00:00+00:00",
        "fixture_count": 0,
        "source_reports": [valid_source_report()],
        "fixtures": [],
        "errors": [],
        "warnings": [],
        "safety": {
            "live_betting_allowed": False,
            "automated_wagering_allowed": False,
            "real_money_betting_allowed": False,
        },
    }


def valid_source_health_report() -> dict:
    return {
        "checked_at": "2026-06-20T00:00:00+00:00",
        "source_reports": [valid_source_report()],
    }


def test_valid_contract_reports_pass(tmp_path: Path) -> None:
    write_json(tmp_path / "report" / "fixture_ingestion_report.json", valid_fixture_ingestion_report())
    write_json(tmp_path / "report" / "source_health_report.json", valid_source_health_report())

    report = validate_data_contract(root=tmp_path)

    assert report["ok"] is True
    assert report["error_count"] == 0
    assert report["issues"] == []


def test_missing_required_reports_do_not_crash(tmp_path: Path) -> None:
    report = validate_data_contract(root=tmp_path)

    assert report["ok"] is False
    assert report["error_count"] == 2
    assert {issue["code"] for issue in report["issues"]} == {"missing_required_report"}


def test_non_finite_json_is_rejected(tmp_path: Path) -> None:
    payload = valid_fixture_ingestion_report()
    payload["fixture_count"] = float("nan")
    write_json(tmp_path / "report" / "fixture_ingestion_report.json", payload, allow_nan=True)
    write_json(tmp_path / "report" / "source_health_report.json", valid_source_health_report())

    report = validate_data_contract(root=tmp_path)

    assert any(issue["code"] == "non_finite_json" for issue in report["issues"])


def test_safety_flags_and_forbidden_keys_are_rejected(tmp_path: Path) -> None:
    payload = valid_fixture_ingestion_report()
    payload["safety"]["live_betting_allowed"] = True
    payload["predictions"] = [{"recommended_bet": "home_win", "stake_size": 10}]
    write_json(tmp_path / "report" / "fixture_ingestion_report.json", payload)
    write_json(tmp_path / "report" / "source_health_report.json", valid_source_health_report())

    report = validate_data_contract(root=tmp_path)
    codes = [issue["code"] for issue in report["issues"]]

    assert "safety_flag_true" in codes
    assert codes.count("forbidden_betting_key") == 2


def test_invalid_source_report_schema_is_rejected(tmp_path: Path) -> None:
    payload = valid_fixture_ingestion_report()
    payload["source_reports"] = [{"source": {}, "attempted": False}]
    write_json(tmp_path / "report" / "fixture_ingestion_report.json", payload)
    write_json(tmp_path / "report" / "source_health_report.json", valid_source_health_report())

    report = validate_data_contract(root=tmp_path)

    assert any(issue["code"] == "invalid_source_report" for issue in report["issues"])


def test_api_key_scanner_flags_real_assignments_but_allows_blank_placeholders(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("API_FOOTBALL_KEY=\nFOOTBALL_DATA_TOKEN=real-token-value\n", encoding="utf-8")

    report = validate_data_contract(root=tmp_path, required_reports=(), tracked_text_paths=(".env",))

    assert report["ok"] is False
    assert report["issues"] == [
        {
            "severity": "error",
            "path": ".env",
            "code": "api_key_in_repo",
            "message": "possible secret assignment on line 2",
        }
    ]


def test_prediction_snapshot_csv_rejects_forbidden_columns_and_true_safety_flags(tmp_path: Path) -> None:
    snapshot_path = tmp_path / "data" / "prediction_snapshots.csv"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["fixture_id", "recommended_bet", "live_betting_allowed"])
        writer.writeheader()
        writer.writerow({"fixture_id": "demo", "recommended_bet": "home", "live_betting_allowed": "true"})

    report = validate_data_contract(root=tmp_path, required_reports=(), tracked_text_paths=())
    codes = [issue["code"] for issue in report["issues"]]

    assert "forbidden_snapshot_column" in codes
    assert "snapshot_safety_flag_true" in codes


def test_write_data_contract_report_outputs_json(tmp_path: Path) -> None:
    write_json(tmp_path / "report" / "fixture_ingestion_report.json", valid_fixture_ingestion_report())
    write_json(tmp_path / "report" / "source_health_report.json", valid_source_health_report())

    report = write_data_contract_report(root=tmp_path)
    saved = json.loads((tmp_path / "report" / "data_contract_report.json").read_text(encoding="utf-8"))

    assert saved["ok"] == report["ok"]
    assert saved["report_type"] == "football_data_contract"
