from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
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


def url_with_query(base_url: str | None, path: str, params: dict[str, str] | None = None) -> str | None:
    if not base_url:
        return None
    query = f"?{urlencode(params)}" if params else ""
    safe_path = path if path.startswith("/") else f"/{path}"
    return f"{base_url.rstrip('/')}{safe_path}{query}"


def sportsdataio_fixture_path(settings) -> str:
    competition_id = (
        getattr(settings, "sportsdataio_world_cup_competition_id", None)
        or getattr(settings, "sportsdataio_world_cup_competition_key", None)
        or "missing_competition_id"
    )
    season_id = (
        getattr(settings, "sportsdataio_world_cup_season_id", None)
        or getattr(settings, "sportsdataio_world_cup_season", None)
        or "missing_season_id"
    )
    template = getattr(
        settings,
        "sportsdataio_world_cup_fixtures_path",
        "/scores/json/GamesByCompetition/{competition_id}/{season_id}",
    )
    return template.format(
        competition_key=competition_id,
        competition_id=competition_id,
        season=season_id,
        season_id=season_id,
    )


def endpoint_for(source_key: str, settings) -> str | None:
    mapping = {
        "football_data": settings.football_data_base_url,
        "api_football": url_with_query(
            settings.api_football_base_url,
            "/fixtures",
            {
                "league": str(settings.api_football_worldcup_league_id),
                "season": str(settings.api_football_worldcup_season),
            },
        ),
        "thestatsapi_worldcup": url_with_query(
            settings.thestatsapi_base_url,
            "/football/matches",
            {
                "competition_id": str(settings.thestatsapi_world_cup_competition_id or ""),
                "season_id": str(settings.thestatsapi_world_cup_season_id or ""),
                "page": "1",
                "per_page": "100",
            },
        ),
        "sportsdataio_worldcup": url_with_query(settings.sportsdataio_base_url, sportsdataio_fixture_path(settings)),
        "fifa_ranking_source": settings.fifa_ranking_url,
        "worldcup_2026_api": url_with_query(settings.worldcup_2026_public_base_url, "/get/games"),
        "tournamental_wc2026": url_with_query(settings.tournamental_wc2026_base_url, "/v1/upcoming"),
        "zafronix_worldcup": url_with_query(settings.zafronix_worldcup_base_url, "/matches", {"year": "2026"}),
        "thesportsdb_worldcup": url_with_query(
            settings.thesportsdb_base_url,
            f"/{settings.thesportsdb_api_key}/eventsseason.php",
            {"id": settings.thesportsdb_world_cup_league_id, "s": settings.thesportsdb_world_cup_season},
        ),
        "statsbomb_open_data": url_with_query(settings.statsbomb_open_data_base_url, "/competitions.json"),
        "open_meteo_weather": url_with_query(
            settings.open_meteo_base_url,
            "/forecast",
            {
                "latitude": "19.4326",
                "longitude": "-99.1332",
                "hourly": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
                "timezone": "auto",
            },
        ),
        "gdelt_news": url_with_query(
            settings.gdelt_doc_base_url,
            "",
            {
                "query": '"World Cup 2026"',
                "mode": "ArtList",
                "format": "json",
                "maxrecords": "10",
            },
        ),
        "openfootball_worldcup_json": settings.openfootball_worldcup_json_url,
        "espn_scoreboard": settings.espn_scoreboard_url,
        "humhub_fwc_2026": url_with_query(settings.humhub_fwc_2026_base_url, "/matches"),
        "tournamental_odds": settings.tournamental_odds_base_url,
        "openfootball_worldcup_text": "https://raw.githubusercontent.com/openfootball/worldcup/master/2026/worldcup.txt",
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
        if source.requires_key:
            probe = {
                "configured": source.configured,
                "reachable": None,
                "status_code": None,
                "error": "requires_key" if not source.configured else "key_source_not_probed",
            }
        else:
            probe = probe_url(endpoint_for(source.key, settings))
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
