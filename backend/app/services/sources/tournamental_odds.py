from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult


class TournamentalOddsAdapter(BaseSourceAdapter):
    """Read-only Tournamental market-consensus adapter.

    This is not The Odds API. It never emits recommended bets or stake sizing. It is kept
    separate from fixture ingestion and is intended only for external-signal / paper tracking.
    """

    source_key = "tournamental_odds"
    produces_fixtures = False

    async def fetch(self) -> SourceAdapterResult:
        enabled = self.bool_setting("tournamental_odds_enabled", False)
        base_url = self.setting("tournamental_odds_base_url")
        configured = bool(base_url)
        if not enabled:
            return self.disabled_result(configured=configured)
        if not base_url:
            return self.missing_url_result(configured=False)
        return self.readiness_result(
            configured=True,
            enabled=True,
            ok=True,
            status="market_consensus_source_not_fixture_ingestion",
            extra_records=[
                {
                    "usage": "market_consensus_external_signal_paper_tracking_only",
                    "no_recommended_bet": True,
                    "no_stake_size": True,
                    "no_real_money_betting": True,
                }
            ],
        )
