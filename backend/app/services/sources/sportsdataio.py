from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class SportsDataIOAdapter(BaseSourceAdapter):
    source_key = "sportsdataio_worldcup"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("sportsdataio_base_url")
        api_key = self.setting("sportsdataio_api_key")
        enabled = self.bool_setting("sportsdataio_enabled", False)
        competition_id = self.setting("sportsdataio_world_cup_competition_id") or self.setting(
            "sportsdataio_world_cup_competition_key"
        )
        season_id = self.setting("sportsdataio_world_cup_season_id") or self.setting("sportsdataio_world_cup_season")
        configured = bool(base_url and api_key)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not api_key:
            return self.missing_credentials_result(configured=bool(base_url), error="sportsdataio_api_key is not configured")
        if not competition_id or not season_id:
            return self.missing_world_cup_ids_result(configured=True)
        path_template = self.setting("sportsdataio_world_cup_fixtures_path", "/scores/json/GamesByCompetition/{competition_id}/{season_id}")
        path = path_template.format(
            competition_id=competition_id,
            competition_key=competition_id,
            season_id=season_id,
            season=season_id,
        )
        url = build_url(base_url, path)
        return await self.fetch_json(
            url,
            headers={"Ocp-Apim-Subscription-Key": api_key, "Accept": "application/json"},
            configured=True,
            enabled=True,
        )
