from __future__ import annotations

from typing import Any

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class ApiFootballAdapter(BaseSourceAdapter):
    source_key = "api_football"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("api_football_base_url")
        api_key = self.setting("api_football_key")
        enabled = self.bool_setting("api_football_enabled", True)
        league_id = self.setting("api_football_worldcup_league_id", 1)
        season = self.setting("api_football_worldcup_season", 2026)
        configured = bool(base_url and api_key)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not api_key:
            return self.missing_credentials_result(configured=bool(base_url), error="api_football_key is not configured")
        if not league_id or not season:
            return self.missing_world_cup_ids_result(configured=True)
        url = build_url(base_url, "/fixtures", {"league": league_id, "season": season})
        return await self.fetch_json(url, headers={"x-apisports-key": api_key}, configured=True, enabled=True)

    def extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("response"), list):
            return [item for item in payload["response"] if isinstance(item, dict)]
        return []
