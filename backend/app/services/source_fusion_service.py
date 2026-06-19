from __future__ import annotations

from app.schemas import DataSourceStatus, SourceFeatureBundle


EXCLUDED_FROM_FIXTURE_RELIABILITY = {
    "scraper",
    "public_market_api",
    "external_prediction_benchmark",
    "offline_training",
    "weather_api",
    "news_api",
    "team_strength_source",
}


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
                role="Deep live data candidate for fixtures, lineups, events, injuries, standings, statistics, and match-day context.",
                notes="Use around match day and cache aggressively because free quotas are limited. Odds are excluded from betting recommendations.",
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
                role="Trial/paid provider candidate for fixtures, groups, standings, match stats, xG, player stats, and historical context.",
                notes="First use only fixtures and standings-style data. Keep odds away from betting recommendations.",
            ),
            DataSourceStatus(
                key="sportsdataio_worldcup",
                name="SportsDataIO FIFA World Cup / Soccer API",
                category="premium_api",
                priority=4,
                reliability=0.76,
                requires_key=True,
                configured=configured["sportsdataio_worldcup"],
                enabled=enabled["sportsdataio_worldcup"],
                role="Trial/paid provider candidate for schedules, scores, standings, lineups, stats, news, images, and optional odds signals.",
                notes="World Cup 2026 identifiers are CompetitionId=21 and SeasonId=368. Odds remain external signal / paper tracking only.",
            ),
            DataSourceStatus(
                key="fifa_ranking_source",
                name="FIFA Men's World Ranking",
                category="team_strength_source",
                priority=5,
                reliability=0.78,
                requires_key=False,
                configured=configured["fifa_ranking_source"],
                enabled=enabled["fifa_ranking_source"],
                role="Official public team ranking and ranking-point baseline for national-team strength priors.",
                notes="Not a JSON fixture API. Use low-frequency snapshots; do not high-frequency scrape.",
            ),
            DataSourceStatus(
                key="worldcup_2026_api",
                name="World Cup 2026 Open Source API",
                category="public_endpoint",
                priority=6,
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
                priority=7,
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
                priority=8,
                reliability=0.70,
                requires_key=True,
                configured=configured["zafronix_worldcup"],
                enabled=enabled["zafronix_worldcup"],
                role="World Cup historical and 2026 fallback candidate for fixtures, teams, players, stadiums, brackets, and standings.",
                notes="Treat as configurable fallback until endpoint stability and response schema are verified.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_json",
                name="OpenFootball worldcup.json",
                category="open_data",
                priority=9,
                reliability=0.64,
                requires_key=False,
                configured=configured["openfootball_worldcup_json"],
                enabled=enabled["openfootball_worldcup_json"],
                role="Public-domain JSON World Cup history and 2026 schedule data for seeding fixtures and offline regression tests.",
                notes="Community-maintained static data. Cross-check with primary APIs before treating as final.",
            ),
            DataSourceStatus(
                key="thesportsdb_worldcup",
                name="TheSportsDB FIFA World Cup",
                category="metadata_api",
                priority=10,
                reliability=0.54,
                requires_key=False,
                configured=configured["thesportsdb_worldcup"],
                enabled=enabled["thesportsdb_worldcup"],
                role="Free metadata, artwork, event metadata, fixtures/results cross-check, team badges, and visual enrichment.",
                notes="Do not use as primary live-score truth. Best for metadata and artwork fallback.",
            ),
            DataSourceStatus(
                key="statsbomb_open_data",
                name="StatsBomb Open Data",
                category="offline_training",
                priority=11,
                reliability=0.80,
                requires_key=False,
                configured=configured["statsbomb_open_data"],
                enabled=enabled["statsbomb_open_data"],
                role="Open event, lineup, match, competition, and selected 360 data for offline model training and xG feature engineering.",
                notes="Not a live fixture source. Keep attribution when publishing analysis.",
            ),
            DataSourceStatus(
                key="open_meteo_weather",
                name="Open-Meteo Weather API",
                category="weather_api",
                priority=12,
                reliability=0.66,
                requires_key=False,
                configured=configured["open_meteo_weather"],
                enabled=enabled["open_meteo_weather"],
                role="Venue temperature, humidity, precipitation, wind, and historical weather features when stadium coordinates are available.",
                notes="Feature source only. It should enrich fixtures after venue coordinates exist, not create fixtures itself.",
            ),
            DataSourceStatus(
                key="gdelt_news",
                name="GDELT DOC API",
                category="news_api",
                priority=13,
                reliability=0.50,
                requires_key=False,
                configured=configured["gdelt_news"],
                enabled=enabled["gdelt_news"],
                role="News, injury, suspension, travel disruption, coach-comment, and qualitative alert monitoring.",
                notes="Unstructured evidence source only. Do not treat a single article as prediction truth.",
            ),
            DataSourceStatus(
                key="tournamental_bot_arena",
                name="Tournamental Open Bot Arena",
                category="external_prediction_benchmark",
                priority=14,
                reliability=0.62,
                requires_key=True,
                configured=configured["tournamental_bot_arena"],
                enabled=enabled["tournamental_bot_arena"],
                role="Read-only bot arena benchmark, match catalogue, odds, injury, and weather reference signals for paper tracking.",
                notes="Not official, not a primary fixture or score source, and not a real-money betting source. Pick submission remains disabled unless explicitly enabled outside ingestion.",
            ),
            DataSourceStatus(
                key="espn_scoreboard",
                name="ESPN Scoreboard Endpoint",
                category="unofficial_public_endpoint",
                priority=15,
                reliability=0.52,
                requires_key=False,
                configured=configured["espn_scoreboard"],
                enabled=enabled["espn_scoreboard"],
                role="No-key scoreboard fallback for match-day scores and status snapshots.",
                notes="Unofficial endpoint. Response structure and availability may change without notice.",
            ),
            DataSourceStatus(
                key="humhub_fwc_2026",
                name="HumHub FWC 2026 Service",
                category="public_endpoint",
                priority=16,
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
                priority=17,
                reliability=0.84,
                requires_key=False,
                configured=configured["tournamental_odds"],
                enabled=enabled["tournamental_odds"],
                role="Public World Cup prediction-market probabilities for match, group qualification, and outright winner markets.",
                notes="Market-consensus probability signal only. Not a betting execution source and not part of fixture ingestion.",
            ),
            DataSourceStatus(
                key="openfootball_worldcup_text",
                name="OpenFootball worldcup text data",
                category="open_data",
                priority=18,
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
                priority=19,
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
                priority=20,
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
            and source.category not in EXCLUDED_FROM_FIXTURE_RELIABILITY
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
            model_adjustment_note="Source registry is active. Fixture confidence is based on configured fixture sources only; weather, news, rankings, market signals, bot arena benchmarks, and offline training data are separate feature sources.",
        )

    def _configured_flags(self) -> dict[str, bool]:
        return {
            "tournamental_odds": bool(getattr(self.settings, "tournamental_odds_base_url", None)),
            "tournamental_wc2026": bool(getattr(self.settings, "tournamental_wc2026_base_url", None)),
            "tournamental_bot_arena": bool(
                getattr(self.settings, "tournamental_api_key", None)
                and getattr(self.settings, "tournamental_base_url", None)
                and getattr(self.settings, "tournamental_tournament_id", None)
            ),
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
                and (
                    getattr(self.settings, "sportsdataio_world_cup_competition_id", None)
                    or getattr(self.settings, "sportsdataio_world_cup_competition_key", None)
                )
                and (
                    getattr(self.settings, "sportsdataio_world_cup_season_id", None)
                    or getattr(self.settings, "sportsdataio_world_cup_season", None)
                )
            ),
            "thesportsdb_worldcup": bool(
                getattr(self.settings, "thesportsdb_base_url", None)
                and getattr(self.settings, "thesportsdb_api_key", None)
                and getattr(self.settings, "thesportsdb_world_cup_league_id", None)
            ),
            "openfootball_worldcup_json": bool(getattr(self.settings, "openfootball_worldcup_json_url", None)),
            "statsbomb_open_data": bool(getattr(self.settings, "statsbomb_open_data_base_url", None)),
            "espn_scoreboard": bool(getattr(self.settings, "espn_scoreboard_url", None)),
            "open_meteo_weather": bool(getattr(self.settings, "open_meteo_base_url", None)),
            "gdelt_news": bool(getattr(self.settings, "gdelt_doc_base_url", None)),
            "fifa_ranking_source": bool(getattr(self.settings, "fifa_ranking_url", None)),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_base_url", None)),
        }

    def _enabled_flags(self) -> dict[str, bool]:
        return {
            "tournamental_odds": bool(getattr(self.settings, "tournamental_odds_enabled", False)),
            "tournamental_wc2026": bool(getattr(self.settings, "tournamental_wc2026_enabled", True)),
            "tournamental_bot_arena": bool(
                getattr(self.settings, "tournamental_enabled", False)
                and getattr(self.settings, "tournamental_enable_read_only_feeds", True)
            ),
            "zafronix_worldcup": bool(getattr(self.settings, "zafronix_worldcup_enabled", False)),
            "football_data": bool(getattr(self.settings, "football_data_enabled", True)),
            "api_football": bool(getattr(self.settings, "api_football_enabled", True)),
            "worldcup_2026_api": bool(getattr(self.settings, "worldcup_2026_api_enabled", False)),
            "thestatsapi_worldcup": bool(getattr(self.settings, "thestatsapi_enabled", False)),
            "sportsdataio_worldcup": bool(getattr(self.settings, "sportsdataio_enabled", False)),
            "thesportsdb_worldcup": bool(getattr(self.settings, "thesportsdb_enabled", False)),
            "openfootball_worldcup_json": bool(getattr(self.settings, "openfootball_worldcup_json_enabled", True)),
            "statsbomb_open_data": bool(getattr(self.settings, "statsbomb_open_data_enabled", True)),
            "espn_scoreboard": True,
            "open_meteo_weather": bool(getattr(self.settings, "open_meteo_enabled", False)),
            "gdelt_news": bool(getattr(self.settings, "gdelt_enabled", False)),
            "fifa_ranking_source": bool(getattr(self.settings, "fifa_ranking_enabled", False)),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_enabled", False)),
        }
