from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class TournamentalWC2026Adapter(BaseSourceAdapter):
    source_key = "tournamental_wc2026"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("tournamental_wc2026_base_url")
        enabled = self.bool_setting("tournamental_wc2026_enabled", True)
        configured = bool(base_url)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not base_url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(build_url(base_url, "/v1/upcoming"), configured=True, enabled=True)
