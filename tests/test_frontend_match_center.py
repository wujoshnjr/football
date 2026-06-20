from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend" / "app" / "page.tsx"


def page_source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_homepage_is_world_cup_match_center_not_diagnostics_first() -> None:
    source = page_source()

    assert "2026 世界盃比賽中心" in source
    assert "明日全部比賽" in source
    assert "已完賽結果" in source
    assert "完整賽程" in source
    assert source.index("2026 世界盃比賽中心") < source.index("id=\"tomorrow\"")
    assert source.index("id=\"tomorrow\"") < source.index("id=\"completed\"")
    assert source.index("id=\"completed\"") < source.index("id=\"schedule\"")
    assert source.index("id=\"schedule\"") < source.index("id=\"diagnostics\"")
    assert "系統狀態與問題診斷" not in source


def test_homepage_uses_single_product_fixture_fetch() -> None:
    source = page_source()

    assert "/fixtures?status=all&tz=Asia/Taipei" in source
    assert "/fixtures/tomorrow?tz=Asia/Taipei" not in source
    assert "/fixtures/completed?tz=Asia/Taipei" not in source
    assert "/data-sources/health" not in source
    assert source.count("getJson<FixturePayload>") == 1
    assert "tomorrowFixtures = schedulePayload.fixtures.filter" in source
    assert "completedSchedule = schedulePayload.fixtures.filter" in source
    assert "upcomingSchedule = schedulePayload.fixtures.filter" in source
    assert "predictionFetchLimit = 3" in source
    assert "Demo fallback" in source
    assert "python scripts/build_worldcup_fixture_cache.py" in source


def test_homepage_keeps_diagnostics_secondary_and_avoids_old_market_primary_signal() -> None:
    source = page_source()

    assert "id=\"diagnostics\"" in source
    assert "Render 可能冷啟動" in source
    assert "tournamental_odds" not in source
    assert "recommended_bet" not in source
    assert "stake_size" not in source
