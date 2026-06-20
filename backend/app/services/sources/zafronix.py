from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class ZafronixWorldCupAdapter(BaseSourceAdapter):
    source_key = "zafronix_worldcup"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("zafronix_worldcup_base_url")
        api_key = self.setting("zafronix_worldcup_key")
        enabled = self.bool_setting("zafronix_worldcup_enabled", False)
        configured = bool(base_url and api_key)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not api_key:
            return self.missing_credentials_result(configured=bool(base_url), error="zafronix_worldcup_key is not configured")
        if not base_url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(
            build_url(base_url, "/matches", {"year": "2026"}),
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            configured=True,
            enabled=True,
        )
