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
from app.services.fixture_ingestion_service import FixtureIngestionService

INTERIM_DIR = ROOT / "data" / "interim"
REPORT_DIR = ROOT / "report"


def main() -> int:
    settings = get_settings()
    payload = FixtureIngestionService(settings).ingest()
    generated_at = datetime.now(timezone.utc).isoformat()

    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    fixture_path = INTERIM_DIR / "normalized_fixtures.json"
    report_path = REPORT_DIR / "fixture_ingestion_report.json"

    report = {
        "generated_at": generated_at,
        "fixture_count": payload["fixture_count"],
        "sources": payload["sources"],
        "usage_note": payload["usage_note"],
    }

    fixture_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {fixture_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
