from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult


class OpenFootballWorldCupAdapter(BaseSourceAdapter):
    source_key = "openfootball_worldcup_json"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        url = self.setting("openfootball_worldcup_json_url")
        enabled = self.bool_setting("openfootball_worldcup_json_enabled", True)
        configured = bool(url)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(url, configured=True, enabled=True)
