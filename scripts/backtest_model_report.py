from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.main import demo_fixtures, source_context
from app.services.model_evaluation_service import summarize_predictions
from app.services.prediction_service import PredictionService

REPORT_DIR = ROOT / "report"


def main() -> int:
    settings = get_settings()
    service = PredictionService(model_version=settings.model_version)
    context = source_context()
    fixtures = demo_fixtures()
    predictions = [(fixture, service.predict_fixture(fixture, source_context=context)) for fixture in fixtures]
    summary = summarize_predictions(predictions)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.model_version,
        "evaluation_scope": "demo_finished_fixtures_only",
        "summary": summary,
        "quality_gate_note": "This is a report format and smoke-test backtest. Do not claim production accuracy until historical fixtures are ingested and temporally validated.",
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "model_backtest_report.json"
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
