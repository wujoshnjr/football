from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class WorldCup2026ApiAdapter(BaseSourceAdapter):
    source_key = "worldcup_2026_api"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("worldcup_2026_public_base_url")
        enabled = self.bool_setting("worldcup_2026_api_enabled", False)
        configured = bool(base_url)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not base_url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(build_url(base_url, "/get/games"), configured=True, enabled=True)
