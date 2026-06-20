from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class HumHubFWC2026Adapter(BaseSourceAdapter):
    source_key = "humhub_fwc_2026"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("humhub_fwc_2026_base_url")
        enabled = self.bool_setting("humhub_fwc_2026_enabled", False)
        configured = bool(base_url)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not base_url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(build_url(base_url, "/matches"), configured=True, enabled=True)
