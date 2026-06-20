from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_pipeline_manifest import (
    TRACKED_ARTIFACTS,
    artifact_summary,
    build_pipeline_manifest,
    write_pipeline_manifest,
)


def test_manifest_tracks_expected_artifacts() -> None:
    assert "report/fixture_ingestion_report.json" in TRACKED_ARTIFACTS
    assert "report/source_health_report.json" in TRACKED_ARTIFACTS
    assert "data/prediction_snapshots.csv" in TRACKED_ARTIFACTS
    assert "data/sample_state.json" in TRACKED_ARTIFACTS


def test_missing_artifacts_do_not_crash(tmp_path: Path) -> None:
    manifest = build_pipeline_manifest(root=tmp_path, artifacts=("report/missing.json", "data/missing.csv"))

    assert manifest["artifact_count"] == 2
    assert manifest["existing_count"] == 0
    assert manifest["missing_count"] == 2
    assert all(item["exists"] is False for item in manifest["artifacts"])
    assert manifest["safety"]["live_betting_allowed"] is False


def test_json_artifact_summary_includes_top_level_keys_and_hash(tmp_path: Path) -> None:
    path = tmp_path / "report" / "fixture_ingestion_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"run_id": "r1", "checked_at": "2026-06-20T00:00:00Z", "fixtures": []}
    raw = json.dumps(payload, sort_keys=True)
    path.write_text(raw, encoding="utf-8")

    summary = artifact_summary(tmp_path, "report/fixture_ingestion_report.json")

    assert summary["exists"] is True
    assert summary["size_bytes"] == len(raw.encode("utf-8"))
    assert summary["sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert summary["json_valid"] is True
    assert summary["json_type"] == "dict"
    assert summary["json_top_level_keys"] == ["checked_at", "fixtures", "run_id"]


def test_invalid_json_is_recorded_not_raised(tmp_path: Path) -> None:
    path = tmp_path / "report" / "bad.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")

    summary = artifact_summary(tmp_path, "report/bad.json")

    assert summary["exists"] is True
    assert summary["json_valid"] is False
    assert summary["json_error"]


def test_csv_artifact_summary_counts_rows(tmp_path: Path) -> None:
    path = tmp_path / "data" / "fixtures.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=["fixture_id", "home_team"])
        writer.writeheader()
        writer.writerow({"fixture_id": "1", "home_team": "Argentina"})
        writer.writerow({"fixture_id": "2", "home_team": "France"})

    summary = artifact_summary(tmp_path, "data/fixtures.csv")

    assert summary["exists"] is True
    assert summary["csv_row_count"] == 2
    assert summary["json_valid"] is None


def test_write_pipeline_manifest_outputs_json(tmp_path: Path) -> None:
    manifest = write_pipeline_manifest(root=tmp_path)
    saved_path = tmp_path / "report" / "pipeline_manifest.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8"))

    assert saved["report_type"] == "football_pipeline_manifest"
    assert saved["artifact_count"] == manifest["artifact_count"]
    assert saved["missing_count"] >= 1
    assert "recommended_bet" not in json.dumps(saved)
    assert "stake_size" not in json.dumps(saved)
