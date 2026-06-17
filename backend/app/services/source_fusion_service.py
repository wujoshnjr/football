from __future__ import annotations

from app.schemas import DataSourceStatus, SourceFeatureBundle


class SourceFusionService:
    def __init__(self, settings) -> None:
        self.settings = settings

    def registry(self) -> list[DataSourceStatus]:
        configured = self._configured_flags()
        return [
            DataSourceStatus(
                key="zafronix_worldcup",
                name="Zafronix World Cup API",
                category="primary_api",
                priority=1,
                reliability=0.82,
                requires_key=True,
                configured=configured["zafronix_worldcup"],
                role="歷史至今完整世界盃資料；適合補歷史戰績、交手與賽事基礎資料。",
                notes="未找到穩定公開文件，先做成可配置 adapter；填入 base url 與 key 後啟用。",
            ),
            DataSourceStatus(
                key="football_data",
                name="football-data.org",
                category="primary_api",
                priority=2,
                reliability=0.86,
                requires_key=True,
                configured=configured["football_data"],
                role="穩定賽程、比分、積分與隊伍資料；適合低頻輪詢。",
                notes="作為 fixture truth source 與備援比分源。",
            ),
            DataSourceStatus(
                key="api_football",
                name="API-Football / RapidAPI",
                category="premium_api",
                priority=3,
                reliability=0.9,
                requires_key=True,
                configured=configured["api_football"],
                role="陣容、事件、傷停、賠率與深度即時資料。",
                notes="免費額度較少，只在比賽日前後或重要更新時呼叫。",
            ),
            DataSourceStatus(
                key="worldcup_2026_public",
                name="World Cup 2026 public API",
                category="public_endpoint",
                priority=4,
                reliability=0.58,
                requires_key=False,
                configured=configured["worldcup_2026_public"],
                role="免 key 即時分組與賽程，用於快速原型與 fallback。",
                notes="公開端點穩定性需監控。",
            ),
            DataSourceStatus(
                key="statsbomb_open_data",
                name="StatsBomb Open Data",
                category="open_data",
                priority=5,
                reliability=0.8,
                requires_key=False,
                configured=True,
                role="事件級資料與 xG 訓練資料，用於模型訓練，不作為即時賽程主源。",
                notes="發布分析時需標示資料來源。",
            ),
            DataSourceStatus(
                key="openfootball_worldcup",
                name="OpenFootball worldcup / worldcup.json",
                category="open_data",
                priority=6,
                reliability=0.62,
                requires_key=False,
                configured=True,
                role="公開領域歷史與 2026 賽程資料；適合離線訓練與備援。",
                notes="社群維護，需與主 API 交叉驗證。",
            ),
            DataSourceStatus(
                key="espn_scoreboard",
                name="ESPN scoreboard endpoint",
                category="unofficial_public_endpoint",
                priority=7,
                reliability=0.52,
                requires_key=False,
                configured=True,
                role="比賽日快速比分與狀態 fallback。",
                notes="非官方接口，格式與可用性可能改變，不作為唯一來源。",
            ),
            DataSourceStatus(
                key="humhub_fwc_2026",
                name="HumHub FWC 2026 service",
                category="public_endpoint",
                priority=8,
                reliability=0.5,
                requires_key=False,
                configured=configured["humhub_fwc_2026"],
                role="免 key 賽程服務 fallback。",
                notes="未找到足夠穩定公開文件，先以可配置 endpoint 形式保留。",
            ),
            DataSourceStatus(
                key="soccerdata_scrapers",
                name="soccerdata / GitHub scrapers",
                category="scraper",
                priority=9,
                reliability=0.44,
                requires_key=False,
                configured=True,
                role="離線研究與補資料，不建議在線上請求同步使用。",
                notes="需遵守來源網站條款、限速與快取。",
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
                model_adjustment_note="尚未配置任何可用 API key；目前只使用本地 demo 與 baseline 模型。",
            )

        weighted = sum(source.reliability / max(source.priority, 1) for source in live_sources)
        max_weighted = sum(1 / max(source.priority, 1) for source in live_sources)
        reliability_score = round(min(weighted / max_weighted, 1.0), 3) if max_weighted else 0.0
        consensus_score = round(min(len(live_sources) / 5, 1.0), 3)

        return SourceFeatureBundle(
            sources_used=[source.key for source in live_sources],
            sources_configured=configured_sources,
            sources_missing=missing_sources,
            reliability_score=reliability_score,
            fixture_consensus_score=consensus_score,
            model_adjustment_note="資料源已進入模型：目前以來源可靠度與來源數量調整 confidence，後續可把實際 fixture/form/odds/xG 特徵寫入 feature table。",
        )

    def _configured_flags(self) -> dict[str, bool]:
        return {
            "zafronix_worldcup": bool(getattr(self.settings, "zafronix_worldcup_key", None) and getattr(self.settings, "zafronix_worldcup_base_url", None)),
            "football_data": bool(getattr(self.settings, "football_data_token", None)),
            "api_football": bool(getattr(self.settings, "api_football_key", None)),
            "worldcup_2026_public": bool(getattr(self.settings, "worldcup_2026_public_base_url", None)),
            "humhub_fwc_2026": bool(getattr(self.settings, "humhub_fwc_2026_base_url", None)),
        }
