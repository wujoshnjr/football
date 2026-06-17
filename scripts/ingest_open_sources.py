from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.config import get_settings
from app.services.source_fusion_service import SourceFusionService

TIMEOUT_SECONDS = 12
OUTPUT_DIR = ROOT / "report"
RAW_DIR = ROOT / "data" / "raw"


def probe_url(url: str | None) -> dict:
    if not url:
        return {"configured": False, "reachable": False, "status_code": None, "error": "missing_url"}

    request = Request(url, headers={"User-Agent": "football-prediction-source-check/1.0"})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return {
                "configured": True,
                "reachable": True,
                "status_code": response.status,
                "content_type": response.headers.get("content-type"),
                "error": None,
            }
    except HTTPError as exc:
        return {"configured": True, "reachable": False, "status_code": exc.code, "error": f"http_{exc.code}"}
    except URLError as exc:
        return {"configured": True, "reachable": False, "status_code": None, "error": str(exc.reason)}
    except TimeoutError:
        return {"configured": True, "reachable": False, "status_code": None, "error": "timeout"}


def endpoint_for(source_key: str, settings) -> str | None:
    mapping = {
        "zafronix_worldcup": settings.zafronix_worldcup_base_url,
        "football_data": settings.football_data_base_url,
        "api_football": settings.api_football_base_url,
        "the_odds_api": settings.the_odds_api_base_url,
        "worldcup_2026_api": settings.worldcup_2026_public_base_url,
        "statsbomb_open_data": settings.statsbomb_open_data_base_url,
        "openfootball_worldcup_json": settings.openfootball_worldcup_json_url,
        "openfootball_worldcup_text": "https://raw.githubusercontent.com/openfootball/worldcup/master/2026/worldcup.txt",
        "espn_scoreboard": settings.espn_scoreboard_url,
        "humhub_fwc_2026": settings.humhub_fwc_2026_base_url,
        "soccerdata_package": settings.soccerdata_project_url,
        "github_football_scrapers": "https://github.com/search?q=football+prediction+scraper&type=repositories",
    }
    return mapping.get(source_key)


def main() -> int:
    settings = get_settings()
    service = SourceFusionService(settings)
    registry = service.registry()
    context = service.build_source_context()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    source_rows = []
    for source in registry:
        probe = probe_url(endpoint_for(source.key, settings)) if not source.requires_key else {"configured": source.configured, "reachable": None, "status_code": None, "error": "requires_key" if not source.configured else "key_source_not_probed"}
        source_rows.append({
            "key": source.key,
            "name": source.name,
            "category": source.category,
            "priority": source.priority,
            "reliability": source.reliability,
            "requires_key": source.requires_key,
            "configured": source.configured,
            "enabled": source.enabled,
            "role": source.role,
            "notes": source.notes,
            "probe": probe,
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_version": settings.model_version,
        "source_context": context.model_dump(),
        "sources": source_rows,
    }

    report_path = OUTPUT_DIR / "data_sources_report.json"
    raw_path = RAW_DIR / "source_registry_snapshot.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    raw_path.write_text(json.dumps(source_rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Wrote {report_path}")
    print(f"Wrote {raw_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
