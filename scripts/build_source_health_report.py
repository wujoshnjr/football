from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.services.sources.base import SourceAdapterResult
from app.services.sources.registry import build_source_adapters

REPORT_PATH = ROOT / "report" / "source_health_report.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def safe_fetch(adapter: Any) -> SourceAdapterResult:
    try:
        return await adapter.fetch()
    except Exception as exc:  # noqa: BLE001 - source health must never crash CI
        return SourceAdapterResult(
            source_key=getattr(adapter, "source_key", "unknown"),
            attempted=True,
            configured=False,
            enabled=False,
            ok=False,
            status="adapter_exception",
            error=str(exc),
            record_count=0,
            records=[],
            generated_at=utc_now(),
            retryable=False,
        )


async def build_report(timeout_seconds: int = 12) -> dict[str, Any]:
    settings = get_settings()
    adapters = build_source_adapters(settings, timeout_seconds=timeout_seconds)
    results = [await safe_fetch(adapter) for adapter in adapters]
    return {
        "report_type": "source_health",
        "generated_at": utc_now(),
        "source_count": len(results),
        "ok_count": sum(1 for result in results if result.ok),
        "sources": [result.to_report_dict(include_records=False) for result in results],
        "usage_note": (
            "Source health checks are read-only. Market, benchmark, weather, news, and ranking sources "
            "must not be treated as fixture truth. This report never triggers real-money betting, "
            "pick submission, recommended bets, or stake sizing."
        ),
    }


def main() -> int:
    report = asyncio.run(build_report())
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
