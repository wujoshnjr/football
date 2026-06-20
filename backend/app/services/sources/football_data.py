from __future__ import annotations

from typing import Any

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult, build_url


class FootballDataAdapter(BaseSourceAdapter):
    source_key = "football_data"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        base_url = self.setting("football_data_base_url")
        token = self.setting("football_data_token")
        enabled = self.bool_setting("football_data_enabled", True)
        configured = bool(base_url and token)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not token:
            return self.missing_credentials_result(configured=bool(base_url), error="football_data_token is not configured")
        competition_code = self.setting("football_data_worldcup_competition_code", "WC")
        url = build_url(base_url, f"/competitions/{competition_code}/matches")
        return await self.fetch_json(url, headers={"X-Auth-Token": token}, configured=True, enabled=True)

    def extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("matches"), list):
            return [item for item in payload["matches"] if isinstance(item, dict)]
        return []
