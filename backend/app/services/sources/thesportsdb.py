from __future__ import annotations

from typing import Any

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class TheSportsDBAdapter(BaseSourceAdapter):
    source_key = "thesportsdb_worldcup"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("thesportsdb_base_url")
        api_key = self.setting("thesportsdb_api_key", "123")
        league_id = self.setting("thesportsdb_world_cup_league_id")
        season = self.setting("thesportsdb_world_cup_season", "2026")
        enabled = self.bool_setting("thesportsdb_enabled", False)
        configured = bool(base_url and api_key and league_id)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not api_key or not league_id:
            return self.missing_credentials_result(configured=bool(base_url), error="TheSportsDB api key or league id is not configured")
        url = build_url(base_url, f"/{api_key}/eventsseason.php", {"id": league_id, "s": season})
        return await self.fetch_json(url, configured=True, enabled=True)

    def extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict):
            events = payload.get("events") or payload.get("event") or []
            if isinstance(events, list):
                return [item for item in events if isinstance(item, dict)]
        return []
