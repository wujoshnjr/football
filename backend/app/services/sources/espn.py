from __future__ import annotations

from typing import Any

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult


class ESPNScoreboardAdapter(BaseSourceAdapter):
    source_key = "espn_scoreboard"
    produces_fixtures = True

    async def fetch(self) -> SourceAdapterResult:
        url = self.setting("espn_scoreboard_url")
        if not url:
            return self.missing_url_result(configured=False)
        return await self.fetch_json(url, configured=True, enabled=True)

    def extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and isinstance(payload.get("events"), list):
            return [item for item in payload["events"] if isinstance(item, dict)]
        return []
