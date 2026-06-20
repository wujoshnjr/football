from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_model_artifact_status import (
    MODEL_SOURCES,
    build_model_artifact_status,
    current_feature_schema_hash,
)
from scripts.football_promotion_gate import build_promotion_gate_report


def test_missing_artifact_falls_back_to_manual_baseline(tmp_path: Path) -> None:
    report = build_model_artifact_status(
        artifact_path=tmp_path / "missing_model.json",
        training_status_path=tmp_path / "missing_training_status.json",
        prediction_snapshots_path=tmp_path / "missing_snapshots.csv",
        output_path=None,
        report_path=None,
    )

    assert report["model_source"] == "manual_baseline"
    assert report["fallback_model_source"] == "manual_baseline"
    assert report["active_model_allowed"] is False
    assert report["production_ready"] is False
    assert "artifact_missing" in report["blockers"]
    assert report["safety"]["live_betting_allowed"] is False


def test_valid_artifact_status_allows_trained_artifact_when_schema_and_samples_pass(tmp_path: Path) -> None:
    artifact_path = tmp_path / "football_model_artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "model_source": "trained_artifact",
                "feature_schema_hash": current_feature_schema_hash(),
                "clean_train_samples": 350,
                "production_samples": 1200,
                "metadata": {"pipeline_version": "football_baseline_v1"},
            }
        ),
        encoding="utf-8",
    )

    report = build_model_artifact_status(
        artifact_path=artifact_path,
        training_status_path=tmp_path / "missing_training_status.json",
        prediction_snapshots_path=tmp_path / "missing_snapshots.csv",
        output_path=None,
        report_path=None,
    )

    assert report["model_source"] == "trained_artifact"
    assert report["active_model_allowed"] is True
    assert report["production_ready"] is True
    assert report["feature_schema_match"] is True
    assert report["allowed_model_sources"] == list(MODEL_SOURCES)


def test_promotion_gate_blocks_low_samples_and_manual_baseline() -> None:
    report = build_promotion_gate_report(
        model_status={
            "model_source": "manual_baseline",
            "clean_train_samples": 20,
            "production_samples": 20,
            "feature_schema_match": False,
            "artifact_feature_schema_hash": "",
        },
        calibration_report={"sample_count": 10, "status": "insufficient_sample"},
        sample_state={},
        data_contract_report={"status": "ok"},
        output_path=None,
    )

    assert report["status"] == "insufficient_samples"
    assert report["production_ready"] is False
    assert "manual_baseline_cannot_claim_production_model" in report["blockers"]
    assert "clean_train_samples_below_300" in report["blockers"]
    assert "settled_predictions_below_500" in report["blockers"]
    assert "production_samples_below_1000" in report["blockers"]
    assert "calibration_report_insufficient_sample" in report["blockers"]


def test_promotion_gate_can_report_production_ready_for_valid_trained_artifact() -> None:
    feature_hash = current_feature_schema_hash()
    report = build_promotion_gate_report(
        model_status={
            "model_source": "trained_artifact",
            "active_model_allowed": True,
            "clean_train_samples": 350,
            "production_samples": 1200,
            "feature_schema_match": True,
            "artifact_feature_schema_hash": feature_hash,
            "safety": {"live_betting_allowed": False, "automated_wagering_allowed": False},
        },
        calibration_report={"sample_count": 600, "status": "ok", "safety": {"live_betting_allowed": False}},
        sample_state={},
        data_contract_report={"status": "ok"},
        output_path=None,
    )

    assert report["status"] == "production_ready"
    assert report["production_ready"] is True
    assert report["active_model_allowed"] is True
    assert report["formal_calibration_allowed"] is True
    assert report["blockers"] == []


def test_feature_schema_hash_mismatch_blocks_ready_claim() -> None:
    report = build_promotion_gate_report(
        model_status={
            "model_source": "trained_artifact",
            "active_model_allowed": True,
            "clean_train_samples": 350,
            "production_samples": 1200,
            "feature_schema_match": False,
            "artifact_feature_schema_hash": "different_hash",
        },
        calibration_report={"sample_count": 600, "status": "ok"},
        sample_state={},
        data_contract_report={"status": "ok"},
        output_path=None,
    )

    assert report["status"] == "blocked"
    assert report["production_ready"] is False
    assert "feature_schema_hash_mismatch" in report["blockers"]


def test_live_safety_flag_blocks_promotion() -> None:
    feature_hash = current_feature_schema_hash()
    report = build_promotion_gate_report(
        model_status={
            "model_source": "trained_artifact",
            "active_model_allowed": True,
            "clean_train_samples": 350,
            "production_samples": 1200,
            "feature_schema_match": True,
            "artifact_feature_schema_hash": feature_hash,
            "safety": {"live_betting_allowed": True},
        },
        calibration_report={"sample_count": 600, "status": "ok"},
        sample_state={},
        data_contract_report={"status": "ok"},
        output_path=None,
    )

    assert report["production_ready"] is False
    assert "live_betting_allowed_must_be_false" in report["blockers"]
    serialized = json.dumps(report, sort_keys=True)
    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized
