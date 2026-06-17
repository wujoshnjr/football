from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.main import demo_fixtures, match_feature_rows
from app.config import get_settings

FEATURE_DIR = ROOT / "data" / "features"
REPORT_DIR = ROOT / "report"


def main() -> int:
    settings = get_settings()
    fixtures = demo_fixtures()
    rows = match_feature_rows()

    FEATURE_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    feature_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.model_version,
        "row_count": len(rows),
        "rows": rows,
    }
    report_payload = {
        "generated_at": feature_payload["generated_at"],
        "model_version": settings.model_version,
        "fixture_count": len(fixtures),
        "feature_row_count": len(rows),
        "target_available_count": sum(1 for row in rows if row["is_final"]),
        "scheduled_count": sum(1 for row in rows if not row["is_final"]),
        "feature_columns": sorted(rows[0].keys()) if rows else [],
        "leakage_policy": "Final score targets are excluded from scheduled fixture feature inputs.",
    }

    feature_path = FEATURE_DIR / "match_features.json"
    report_path = REPORT_DIR / "feature_table_report.json"
    feature_path.write_text(json.dumps(feature_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {feature_path}")
    print(f"Wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
