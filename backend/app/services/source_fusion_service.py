from __future__ import annotations

from app.schemas import DataSourceStatus, SourceFeatureBundle


class SourceFusionService:
    def __init__(self, settings) -> None:
        self.settings = settings

    def registry(self) -> list[DataSourceStatus]:
        configured = self._configured_flags()
        enabled = self._enabled_flags()
        return [
            DataSourceStatus(
                key="football_data",
                name="football-data.org API v4",
                category="primary_api",
                priority=1,
                reliability=0.86,
                requires_key=True,
                configured=configured["football_data"],
                enabled=enabled["football_data"],
                role="Stable fixtures, scores, competitions, standings, teams, and low-frequency match updates.",
                notes="Recommended as a fixture truth source and fixture cache cross-check.",
            ),
            DataSourceStatus(
                key="api_football",
                name="API-Football API v3",
                category="premium_api",
                priority=2,
                reliability=0.90,
                requires_key=True,
                configured=configured["api_football"],
                enabled=enabled["api_football"],
                role="Deep live data candidate for fixtures, lineups, events, injuries, standings, and match-day context.",
                notes="Use around match day and cache aggressively because free quotas are limited.",
            ),
            DataSourceStatus(
                key="thestatsapi_worldcup",
                name="TheStatsAPI Football - World Cup 2026",
                category="premium_api",
                priority=3,
                reliability=0.84,
                requires_key=True,
                configured=configured["thestatsapi_worldcup"],
                enabled=enabled["thestatsapi_worldcup"],
                role="Trial/paid provider candidate for fixtures, groups, standings, match stats, xG, and player stats.",
                notes="First use only fixtures and standings-style data. Keep odds away from betting recommendations.",
            ),
            DataSourceStatus(
                key="worldcup_2026_api",
                name="World Cup 2026 Public API",
                category="public_endpoint",
                priority=4,
                reliability=0.58,
                requires_key=False,
                configured=configured["worldcup_2026_api"],
                enabled=enabled["worldcup_2026_api"],
                role="No-key public 2026 World Cup schedule, groups, teams, stadiums, and fallback fixture endpoint.",
                notes="Not an official FIFA source. Use as free fallback and cross-check only.",
            ),
            DataSourceStatus(
                key="tournamental_wc2026",
                name="Tournamental WC2026 Live Data",
                category="public_endpoint",
                priority=5,
                reliability=0.72,
                requires_key=False,
                configured=configured["tournamental_wc2026"],
                enabled=enabled["tournamental_wc2026"],
                role="Public read-only World Cup 2026 match-state, upcoming-match, and match-detail data.",
                notes="Use to map Tournamental match IDs to fixtures and to cross-check match state.",
            ),
            DataSourceStatus(
                key="zafronix_worldcup",
                name="Zafronix World Cup API",
                category="primary_api",
                priority=6,
                reliability=0.70,
                requires_key=True,
                configured=configured["zafronix_worldcup"],
                enabled=enabled["zafronix_worldcup"],
                role="World Cup historical and 2026 fallback candidate for fixtures, teams, players, stadiums, brackets, and standings.",
                notes="Treat as configurable fallback until endpoint stability and response schema are verified.",
            ),
            DataSourceStatus(
                key="sportsdataio_worldcup",
                name="SportsDataIO FIFA World Cup / Soccer API",
                category="premium_api",
                priority=7,
                reliability=0.72,
                requires_key=True,
                configured=configured["sportsdataio_worldcup"],
                enabled=enabled["sportsdataio_worldcup"],
                role="Trial/paid candidate for real-time scores, fixtures, lineups, stats, odds, and historical data.",
                notes="Use only when competition key and plan access are confirmed. Odds remain external signal / paper tracking only.",
            ),
            DataSourceStatus(
                key="thesportsdb_worldcup",
                name="TheSportsDB FIFA World Cup",
                category="metadata_api",
                priority=8,
                reliability=0.54,
                requires_key=False,
                configured=configured["thesportsdb_worldcup"],
                enabled=enabled["thesportsdb_worldcup"],
                role="Free metadata, artwork, event metadata, fixtures/results cross-check, team badges, and visual enrichment.",
                notes="Do not use as primary live-score truth. Best for metadata and artwork fallback.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_json",
                name="OpenFootball worldcup.json",
                category="open_data",
                priority=9,
                reliability=0.64,
                requires_key=False,
                configured=True,
                enabled=True,
                role="Public-domain JSON World Cup history and 2026 schedule data for seeding fixtures and offline regression tests.",
                notes="Community-maintained data. Cross-check with primary APIs before treating as final.",
            ),
            DataSourceStatus(
                key="espn_scoreboard",
                name="ESPN Scoreboard Endpoint",
                category="unofficial_public_endpoint",
                priority=10,
                reliability=0.52,
                requires_key=False,
                configured=True,
                enabled=True,
                role="No-key scoreboard fallback for match-day scores and status snapshots.",
                notes="Unofficial endpoint. Response structure and availability may change without notice.",
            ),
            DataSourceStatus(
                key="humhub_fwc_2026",
                name="HumHub FWC 2026 Service",
                category="public_endpoint",
                priority=11,
                reliability=0.46,
                requires_key=False,
                configured=configured["humhub_fwc_2026"],
                enabled=enabled["humhub_fwc_2026"],
                role="No-key 2026 World Cup schedule fallback service candidate.",
                notes="No sufficiently stable public documentation was verified. Keep as configurable endpoint until validated.",
            ),
            DataSourceStatus(
                key="tournamental_odds",
                name="Tournamental Odds Ingest",
                category="public_market_api",
                priority=12,
                reliability=0.84,
                requires_key=False,
                configured=configured["tournamental_odds"],
                enabled=enabled["tournamental_odds"],
                role="Public World Cup prediction-market probabilities for match, group qualification, and outright winner markets.",
                notes="Market-consensus probability signal only. Not a betting execution source and not part of fixture ingestion.",
            ),
            DataSourceStatus(
                key="statsbomb_open_data",
                name="StatsBomb Open Data",
                category="open_data",
                priority=13,
                reliability=0.80,
                requires_key=False,
                configured=True,
                enabled=True,
                role="Open event, lineup, match, competition, and selected 360 data for offline model training and xG feature engineering.",
                notes="Not a live fixture source. Keep attribution when publishing analysis.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_text",
                name="OpenFootball worldcup text data",
                category="open_data",
                priority=14,
                reliability=0.60,
                requires_key=False,
                configured=True,
                enabled=True,
                role="Upstream text-based World Cup dataset used as an additional open-data cross-check.",
                notes="Useful for historical coverage and backup fixture validation.",
            ),
            DataSourceStatus(
                key="soccerdata_package",
                name="soccerdata Python package",
                category="scraper",
                priority=15,
                reliability=0.46,
                requires_key=False,
                configured=True,
                enabled=True,
                role="Offline research and supplemental ingestion package for football statistics sources.",
                notes="Do not use for synchronous production requests. Respect source terms, rate limits, and caching.",
            ),
            DataSourceStatus(
                key="github_football_scrapers",
                name="GitHub football scraper projects",
                category="scraper",
                priority=16,
                reliability=0.40,
                requires_key=False,
                configured=True,
                enabled=True,
                role="Reference implementations for ingestion architecture and emergency backfill tasks.",
                notes="Use only as inspiration or offline tooling. Production ingestion should use adapters with validation and caching.",
            ),
        ]

    def build_source_context(self) -> SourceFeatureBundle:
        registry = self.registry()
        configured_sources = [source.key for source in registry if source.configured]
        missing_sources = [source.key for source in registry if source.requires_key and not source.configured]

        live_sources = [
            source for source in registry
            if source.configured
            and source.enabled
            and source.category not in {"scraper", "public_market_api"}
        ]
        if not live_sources:
            return SourceFeatureBundle(
                sources_used=[],
                sources_configured=configured_sources,
                sources_missing=missing_sources,
                reliability_score=0.0,
                fixture_consensus_score=0.0,
                model_adjustment_note="No live or public fixture source is active yet. The app is using cached or demo fixtures and the baseline model.",
            )

        weighted = sum(source.reliability / max(source.priority, 1) for source in live_sources)
        max_weighted = sum(1 / max(source.priority, 1) for source in live_sources)
        reliability_score = round(min(weighted / max_weighted, 1.0), 3) if max_weighted else 0.0
        consensus_score = round(min(len(live_sources) / 8, 1.0), 3)

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
            "zafronix_worldcup": bool(
                getattr(self.settings, "zafronix_worldcup_key", None)
                and getattr(self.settings, "zafronix_worldcup_base_url", None)
            ),
            "football_data": bool(getattr(self.settings, "football_data_token", None)),
            "api_football": bool(getattr(self.settings, "api_football_key", None)),
            "worldcup_2026_api": bool(getattr(self.settings, "worldcup_2026_public_base_url", None)),
            "thestatsapi_worldcup": bool(
                getattr(self.settings, "thestatsapi_key", None)
                and getattr(self.settings, "thestatsapi_base_url", None)
                and getattr(self.settings, "thestatsapi_world_cup_competition_id", None)
                and getattr(self.settings, "thestatsapi_world_cup_season_id", None)
            ),
            "sportsdataio_worldcup": bool(
                getattr(self.settings, "sportsdataio_api_key", None)
                and getattr(self.settings, "sportsdataio_base_url", None)
                and getattr(self.settings, "sportsdataio_world_cup_competition_key", None)
            ),
            "thesportsdb_worldcup": bool(
                getattr(self.settings, "thesportsdb_base_url", None)
                and getattr(self.settings, "thesportsdb_api_key", None)
                and getattr(self.settings, "thesportsdb_world_cup_league_id", None)
            ),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_base_url", None)),
        }

    def _enabled_flags(self) -> dict[str, bool]:
        return {
            "tournamental_odds": bool(getattr(self.settings, "tournamental_odds_enabled", False)),
            "tournamental_wc2026": bool(getattr(self.settings, "tournamental_wc2026_enabled", True)),
            "zafronix_worldcup": bool(getattr(self.settings, "zafronix_worldcup_enabled", False)),
            "football_data": bool(getattr(self.settings, "football_data_enabled", True)),
            "api_football": bool(getattr(self.settings, "api_football_enabled", True)),
            "worldcup_2026_api": bool(getattr(self.settings, "worldcup_2026_api_enabled", False)),
            "thestatsapi_worldcup": bool(getattr(self.settings, "thestatsapi_enabled", False)),
            "sportsdataio_worldcup": bool(getattr(self.settings, "sportsdataio_enabled", False)),
            "thesportsdb_worldcup": bool(getattr(self.settings, "thesportsdb_enabled", False)),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_enabled", False)),
        }
