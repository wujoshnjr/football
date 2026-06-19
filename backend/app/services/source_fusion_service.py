from __future__ import annotations

from app.schemas import DataSourceStatus, SourceFeatureBundle


class SourceFusionService:
    def __init__(self, settings) -> None:
        self.settings = settings

    def registry(self) -> list[DataSourceStatus]:
        configured = self._configured_flags()
        return [
            DataSourceStatus(
                key="tournamental_odds",
                name="Tournamental Odds Ingest",
                category="public_market_api",
                priority=1,
                reliability=0.84,
                requires_key=False,
                configured=configured["tournamental_odds"],
                role="Public live World Cup prediction-market probabilities for match, group qualification, and outright winner markets.",
                notes="Use as market-consensus probability signal only; do not treat as a betting execution source.",
            ),
            DataSourceStatus(
                key="tournamental_wc2026",
                name="Tournamental WC2026 Live Data",
                category="public_endpoint",
                priority=2,
                reliability=0.72,
                requires_key=False,
                configured=configured["tournamental_wc2026"],
                role="Public read-only World Cup 2026 match-state, upcoming-match, and match-detail data.",
                notes="Use to map Tournamental match IDs to fixtures and to cross-check match state.",
            ),
            DataSourceStatus(
                key="zafronix_worldcup",
                name="Zafronix World Cup API",
                category="primary_api",
                priority=3,
                reliability=0.82,
                requires_key=True,
                configured=configured["zafronix_worldcup"],
                role="Historical and live World Cup dataset candidate for fixtures, teams, head-to-head history, and tournament context.",
                notes="No stable public documentation was verified yet. It remains a configurable adapter and becomes active when base URL and key are provided.",
            ),
            DataSourceStatus(
                key="football_data",
                name="football-data.org API v4",
                category="primary_api",
                priority=4,
                reliability=0.86,
                requires_key=True,
                configured=configured["football_data"],
                role="Stable fixtures, scores, competitions, standings, teams, and low-frequency match updates.",
                notes="Recommended as a fixture truth source and commercial API fallback source.",
            ),
            DataSourceStatus(
                key="api_football",
                name="API-Football API v3",
                category="premium_api",
                priority=5,
                reliability=0.90,
                requires_key=True,
                configured=configured["api_football"],
                role="Deep live data candidate for fixtures, lineups, events, injuries, standings, and predictions.",
                notes="Use around match day and cache aggressively because free quotas are limited.",
            ),
            DataSourceStatus(
                key="worldcup_2026_api",
                name="World Cup 2026 Public API",
                category="public_endpoint",
                priority=6,
                reliability=0.58,
                requires_key=False,
                configured=configured["worldcup_2026_api"],
                role="No-key public 2026 World Cup schedule and group-stage endpoint for prototype ingestion and fallback checks.",
                notes="Public endpoint reliability must be monitored. Use only after URL validation.",
            ),
            DataSourceStatus(
                key="statsbomb_open_data",
                name="StatsBomb Open Data",
                category="open_data",
                priority=7,
                reliability=0.80,
                requires_key=False,
                configured=True,
                role="Open event, lineup, match, competition, and selected 360 data for offline model training and xG feature engineering.",
                notes="Not a live fixture source. Keep attribution when publishing analysis.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_json",
                name="OpenFootball worldcup.json",
                category="open_data",
                priority=8,
                reliability=0.64,
                requires_key=False,
                configured=True,
                role="Public-domain JSON World Cup history and 2026 schedule data for seeding fixtures and offline regression tests.",
                notes="Community-maintained data. Cross-check with primary APIs before treating as final.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_text",
                name="OpenFootball worldcup text data",
                category="open_data",
                priority=9,
                reliability=0.60,
                requires_key=False,
                configured=True,
                role="Upstream text-based World Cup dataset used as an additional open-data cross-check.",
                notes="Useful for historical coverage and backup fixture validation.",
            ),
            DataSourceStatus(
                key="espn_scoreboard",
                name="ESPN Scoreboard Endpoint",
                category="unofficial_public_endpoint",
                priority=10,
                reliability=0.52,
                requires_key=False,
                configured=True,
                role="No-key scoreboard fallback for match-day scores and status snapshots.",
                notes="Unofficial endpoint. Response structure and availability may change without notice.",
            ),
            DataSourceStatus(
                key="humhub_fwc_2026",
                name="HumHub FWC 2026 Service",
                category="public_endpoint",
                priority=11,
                reliability=0.50,
                requires_key=False,
                configured=configured["humhub_fwc_2026"],
                role="No-key 2026 World Cup schedule fallback service candidate.",
                notes="No sufficiently stable public documentation was verified. Keep as configurable endpoint until validated.",
            ),
            DataSourceStatus(
                key="soccerdata_package",
                name="soccerdata Python package",
                category="scraper",
                priority=12,
                reliability=0.46,
                requires_key=False,
                configured=True,
                role="Offline research and supplemental ingestion package for football statistics sources.",
                notes="Do not use for synchronous production requests. Respect source terms, rate limits, and caching.",
            ),
            DataSourceStatus(
                key="github_football_scrapers",
                name="GitHub football scraper projects",
                category="scraper",
                priority=13,
                reliability=0.40,
                requires_key=False,
                configured=True,
                role="Reference implementations for ingestion architecture and emergency backfill tasks.",
                notes="Use only as inspiration or offline tooling. Production ingestion should use adapters with validation and caching.",
            ),
        ]

    def build_source_context(self) -> SourceFeatureBundle:
        registry = self.registry()
        configured_sources = [source.key for source in registry if source.configured and source.enabled]
        missing_sources = [source.key for source in registry if source.requires_key and not source.configured]

        live_sources = [
            source for source in registry
            if source.configured and source.enabled and source.category != "scraper"
        ]
        if not live_sources:
            return SourceFeatureBundle(
                sources_used=[],
                sources_configured=configured_sources,
                sources_missing=missing_sources,
                reliability_score=0.0,
                fixture_consensus_score=0.0,
                model_adjustment_note="No live or public data source is active yet. The app is using local demo fixtures and the baseline model.",
            )

        weighted = sum(source.reliability / max(source.priority, 1) for source in live_sources)
        max_weighted = sum(1 / max(source.priority, 1) for source in live_sources)
        reliability_score = round(min(weighted / max_weighted, 1.0), 3) if max_weighted else 0.0
        consensus_score = round(min(len(live_sources) / 6, 1.0), 3)

        return SourceFeatureBundle(
            sources_used=[source.key for source in live_sources],
            sources_configured=configured_sources,
            sources_missing=missing_sources,
            reliability_score=reliability_score,
            fixture_consensus_score=consensus_score,
            model_adjustment_note="Source registry is active. Current model confidence is adjusted by source reliability and source coverage; next phase should persist actual fixture, form, market, and xG features into a feature table.",
        )

    def _configured_flags(self) -> dict[str, bool]:
        return {
            "tournamental_odds": bool(getattr(self.settings, "tournamental_odds_base_url", None)),
            "tournamental_wc2026": bool(getattr(self.settings, "tournamental_wc2026_base_url", None)),
            "zafronix_worldcup": bool(getattr(self.settings, "zafronix_worldcup_key", None) and getattr(self.settings, "zafronix_worldcup_base_url", None)),
            "football_data": bool(getattr(self.settings, "football_data_token", None)),
            "api_football": bool(getattr(self.settings, "api_football_key", None)),
            "worldcup_2026_api": bool(getattr(self.settings, "worldcup_2026_public_base_url", None)),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_base_url", None)),
        }
