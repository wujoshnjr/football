from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.football_snapshot_store import (
    append_first_seen_pregame_snapshots,
    build_snapshot_row,
    infer_1x2_result,
    read_snapshot_rows,
    settle_snapshots,
    validate_pregame_prediction,
)


def pregame_prediction(**overrides):
    payload = {
        "fixture_id": "arg-fra-final",
        "kickoff_time": "2026-07-19T19:00:00Z",
        "status": "scheduled",
        "home_team": "Argentina",
        "away_team": "France",
        "stage": "Final",
        "model_version": "test-v1",
        "model_source": "manual_baseline",
        "probabilities": {"home_win": 0.41, "draw": 0.28, "away_win": 0.31},
        "confidence": "medium",
        "features": {"home_elo": 2140, "away_elo": 2050},
        "source_provenance": [{"source_key": "football_data", "source_event_id": "100"}],
    }
    payload.update(overrides)
    return payload


def test_validate_pregame_prediction_accepts_clean_pregame_snapshot() -> None:
    valid, reason = validate_pregame_prediction(
        pregame_prediction(),
        snapshot_created_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert valid is True
    assert reason == ""


def test_build_snapshot_row_supports_football_1x2_probabilities() -> None:
    row = build_snapshot_row(
        pregame_prediction(),
        snapshot_created_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert row["snapshot_valid"] == "true"
    assert row["home_win_prob"] == "0.41"
    assert row["draw_prob"] == "0.28"
    assert row["away_win_prob"] == "0.31"
    assert row["predicted_outcome"] == "home_win"
    assert row["live_betting_allowed"] == "false"
    assert row["automated_wagering_allowed"] == "false"
    assert row["real_money_betting_allowed"] == "false"
    assert json.loads(row["source_provenance_json"])[0]["source_key"] == "football_data"


def test_append_first_seen_pregame_snapshot_inserts_once(tmp_path: Path) -> None:
    path = tmp_path / "prediction_snapshots.csv"
    observed_at = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    first = append_first_seen_pregame_snapshots([pregame_prediction()], path=path, snapshot_created_at=observed_at)
    second = append_first_seen_pregame_snapshots([pregame_prediction()], path=path, snapshot_created_at=observed_at)
    rows = read_snapshot_rows(path)

    assert first["inserted"] == 1
    assert second["duplicates"] == 1
    assert len(rows) == 1
    assert rows[0]["fixture_id"] == "arg-fra-final"


def test_post_kickoff_or_finished_rows_are_not_clean_snapshots(tmp_path: Path) -> None:
    path = tmp_path / "prediction_snapshots.csv"
    late_result = append_first_seen_pregame_snapshots(
        [pregame_prediction()],
        path=path,
        snapshot_created_at=datetime(2026, 7, 19, 20, 0, tzinfo=timezone.utc),
    )
    finished_result = append_first_seen_pregame_snapshots(
        [pregame_prediction(status="finished")],
        path=path,
        snapshot_created_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
    )

    assert late_result["inserted"] == 0
    assert late_result["skipped"] == {"snapshot_created_after_kickoff": 1}
    assert finished_result["inserted"] == 0
    assert finished_result["skipped"] == {"not_confirmed_pregame_status:finished": 1}
    assert read_snapshot_rows(path) == []


def test_settlement_writes_results_without_mutating_pregame_features(tmp_path: Path) -> None:
    path = tmp_path / "prediction_snapshots.csv"
    observed_at = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    append_first_seen_pregame_snapshots([pregame_prediction()], path=path, snapshot_created_at=observed_at)
    before = read_snapshot_rows(path)[0]

    settlement = settle_snapshots(
        [{"fixture_id": "arg-fra-final", "home_score": 2, "away_score": 1}],
        path=path,
        settled_at=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
    )
    after = read_snapshot_rows(path)[0]

    assert settlement["updated"] == 1
    assert after["settlement_status"] == "settled"
    assert after["final_home_score"] == "2"
    assert after["final_away_score"] == "1"
    assert after["result"] == "home_win"
    for key, value in before.items():
        if key not in {"settled_at", "final_home_score", "final_away_score", "result", "advance_result", "settlement_status"}:
            assert after[key] == value


def test_settlement_supports_draw_and_knockout_advance_result(tmp_path: Path) -> None:
    path = tmp_path / "prediction_snapshots.csv"
    observed_at = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)
    append_first_seen_pregame_snapshots([pregame_prediction(fixture_id="ned-jpn-ko")], path=path, snapshot_created_at=observed_at)

    settlement = settle_snapshots(
        [{"fixture_id": "ned-jpn-ko", "home_score": 1, "away_score": 1, "advance_result": "away_advance"}],
        path=path,
    )
    row = read_snapshot_rows(path)[0]

    assert settlement["updated"] == 1
    assert row["result"] == "draw"
    assert row["advance_result"] == "away_advance"


def test_infer_1x2_result() -> None:
    assert infer_1x2_result(2, 1) == "home_win"
    assert infer_1x2_result(1, 2) == "away_win"
    assert infer_1x2_result(1, 1) == "draw"


def test_snapshot_rows_do_not_include_forbidden_betting_keys() -> None:
    row = build_snapshot_row(
        pregame_prediction(),
        snapshot_created_at=datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc),
    )
    serialized = json.dumps(row)

    assert "recommended_bet" not in serialized
    assert "stake_size" not in serialized
