from __future__ import annotations

from app.services.sources.base import BaseSourceAdapter, SourceAdapterResult


class FeatureReadinessAdapter(BaseSourceAdapter):
    """Base for sources that provide model context but do not create fixtures."""

    produces_fixtures = False
    enabled_attr = ""
    configured_attrs: tuple[str, ...] = ()
    ready_status = "feature_source_not_fixture_ingestion"

    async def fetch(self) -> SourceAdapterResult:
        configured = all(bool(self.setting(attr)) for attr in self.configured_attrs)
        enabled = self.bool_setting(self.enabled_attr, False) if self.enabled_attr else True
        if not enabled:
            return self.disabled_result(configured=configured)
        if not configured:
            return self.missing_url_result(configured=False)
        return self.readiness_result(configured=True, enabled=True, status=self.ready_status, ok=True)


class FifaRankingSourceAdapter(FeatureReadinessAdapter):
    source_key = "fifa_ranking_source"
    enabled_attr = "fifa_ranking_enabled"
    configured_attrs = ("fifa_ranking_url",)
    ready_status = "ranking_snapshot_source_not_fixture_ingestion"


class OpenMeteoWeatherAdapter(FeatureReadinessAdapter):
    source_key = "open_meteo_weather"
    enabled_attr = "open_meteo_enabled"
    configured_attrs = ("open_meteo_base_url", "open_meteo_archive_base_url")
    ready_status = "weather_feature_source_not_fixture_ingestion"


class GdeltNewsAdapter(FeatureReadinessAdapter):
    source_key = "gdelt_news"
    enabled_attr = "gdelt_enabled"
    configured_attrs = ("gdelt_doc_base_url",)
    ready_status = "news_signal_source_not_fixture_ingestion"


class StatsBombOpenDataAdapter(FeatureReadinessAdapter):
    source_key = "statsbomb_open_data"
    enabled_attr = "statsbomb_open_data_enabled"
    configured_attrs = ("statsbomb_open_data_base_url",)
    ready_status = "offline_training_source_not_fixture_ingestion"
