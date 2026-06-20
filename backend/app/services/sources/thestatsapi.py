from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class TheStatsApiAdapter(BaseSourceAdapter):
    source_key = "thestatsapi_worldcup"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("thestatsapi_base_url")
        api_key = self.setting("thestatsapi_key")
        enabled = self.bool_setting("thestatsapi_enabled", False)
        competition_id = self.setting("thestatsapi_world_cup_competition_id")
        season_id = self.setting("thestatsapi_world_cup_season_id")
        configured = bool(base_url and api_key)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not api_key:
            return self.missing_credentials_result(configured=bool(base_url), error="thestatsapi_key is not configured")
        if not competition_id or not season_id:
            return self.missing_world_cup_ids_result(configured=True)
        url = build_url(
            base_url,
            "/football/matches",
            {"competition_id": competition_id, "season_id": season_id, "page": 1, "per_page": 100},
        )
        return await self.fetch_json(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            configured=True,
            enabled=True,
        )
