from app.services.tournamental_odds_normalizer import find_market_signal_for_fixture, normalize_tournamental_snapshot
from app.schemas import Fixture, TeamSnapshot


def _team(name: str) -> TeamSnapshot:
    return TeamSnapshot(
        id=name.lower().replace(" ", "-"),
        name=name,
        country=name,
        fifa_rank=None,
        elo_rating=1500,
        recent_points_per_match=1.4,
        goals_for_per_match=1.2,
        goals_against_per_match=1.2,
    )


def test_normalize_snapshot_splits_market_types_and_flags_settled_matches():
    payload = {
        "source_key": "tournamental_odds",
        "data": {
            "ts": 1781791152387,
            "market_count": 4,
            "probabilities": {
                "wc2026:match:57": {"Argentina": 0.6181, "Draw": 0.2362, "Austria": 0.1457},
                "wc2026:match:55": {"Algeria": 0, "Argentina": 1, "Draw": 0},
                "wc2026:group:ARG": {"Yes": 0.835},
                "wc2026:winner:FRA": {"No": 0.8155, "Yes": 0.1845},
            },
        },
    }

    normalized = normalize_tournamental_snapshot(payload)

    assert normalized["match_market_count"] == 2
    assert normalized["usable_match_market_count"] == 1
    assert normalized["group_market_count"] == 1
    assert normalized["winner_market_count"] == 1
    assert normalized["match_markets"][0]["match_no"] == "55"
    assert "settled_like" in normalized["match_markets"][0]["quality_flags"]
    assert normalized["match_markets"][1]["team_key"] == "argentina__austria"


def test_find_market_signal_for_fixture_maps_home_draw_away_probabilities():
    payload = {
        "data": {
            "probabilities": {
                "wc2026:match:57": {"Argentina": 0.6181, "Draw": 0.2362, "Austria": 0.1457},
            },
        },
    }
    normalized = normalize_tournamental_snapshot(payload)
    fixture = Fixture(
        id="arg-aut-2026",
        home_team=_team("Argentina"),
        away_team=_team("Austria"),
        kickoff_time="2026-06-22",
    )

    signal = find_market_signal_for_fixture(fixture, normalized)

    assert signal is not None
    assert signal["market_signal_available"] is True
    assert signal["market_source"] == "tournamental_odds"
    assert signal["market_match_no"] == "57"
    assert signal["market_home_implied_probability"] == 0.6181
    assert signal["market_draw_implied_probability"] == 0.2362
    assert signal["market_away_implied_probability"] == 0.1457
