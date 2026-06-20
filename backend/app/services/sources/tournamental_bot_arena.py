from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult


class TournamentalBotArenaAdapter(BaseSourceAdapter):
    """Read-only readiness adapter for the Tournamental Bot Arena.

    This adapter intentionally does not submit picks and does not create fixtures. It only
    reports whether the benchmark/read-only configuration is safe and ready.
    """

    source_key = "tournamental_bot_arena"
    produces_fixtures = False

    async def fetch(self) -> SourceAdapterResult:
        enabled = self.bool_setting("tournamental_enabled", False)
        read_only_enabled = self.bool_setting("tournamental_enable_read_only_feeds", True)
        pick_submission_enabled = self.bool_setting("tournamental_enable_pick_submission", False)
        base_url = self.setting("tournamental_base_url")
        api_key = self.setting("tournamental_api_key")
        tournament_id = self.setting("tournamental_tournament_id")
        bot_id = self.setting("tournamental_bot_id")
        configured = bool(base_url and api_key and tournament_id)

        if not enabled:
            return self.disabled_result(configured=configured)
        if not read_only_enabled:
            return self.readiness_result(
                configured=configured,
                enabled=False,
                ok=False,
                status="read_only_feeds_disabled",
                error="TOURNAMENTAL_ENABLE_READ_ONLY_FEEDS is false",
            )
        if not api_key:
            return self.missing_credentials_result(configured=bool(base_url), error="tournamental_api_key is not configured")
        if not base_url:
            return self.missing_url_result(configured=False)
        if not tournament_id:
            return self.readiness_result(configured=False, enabled=False, ok=False, status="missing_tournament_id")

        status = (
            "read_only_ready_pick_submission_not_used_by_ingestion"
            if pick_submission_enabled
            else "read_only_benchmark_not_fixture_ingestion"
        )
        return self.readiness_result(
            configured=True,
            enabled=True,
            ok=True,
            status=status,
            extra_records=[
                {
                    "mode": self.setting("tournamental_mode", "bot_arena_benchmark"),
                    "tournament_id": tournament_id,
                    "has_bot_id": bool(bot_id),
                    "pick_submission_enabled": bool(pick_submission_enabled),
                    "safety_note": "adapter does not submit picks or trigger live betting",
                }
            ],
        )
