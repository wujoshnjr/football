import pytest

from app.safety_policy import (
    ALLOWED_MARKET_DATA_ROLES,
    LOCKED_FLAG_ENV_VARS,
    build_safety_policy,
    enforce_no_forbidden_output_keys,
    find_forbidden_output_keys,
)


def test_safety_policy_defaults_are_locked_false(monkeypatch):
    for env_var in LOCKED_FLAG_ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)

    policy = build_safety_policy()
    public = policy.to_public_dict()

    assert public["live_betting"] is False
    assert public["live_betting_locked"] is True
    assert public["automated_wagering"] is False
    assert public["automated_wagering_locked"] is True
    assert public["tournamental_pick_submission"] is False
    assert public["tournamental_pick_submission_locked"] is True
    assert public["market_data_allowed_roles"] == list(ALLOWED_MARKET_DATA_ROLES)
    assert public["ignored_enable_requests"] == []
    assert find_forbidden_output_keys(public) == ()


def test_env_requests_cannot_unlock_betting_or_pick_submission(monkeypatch):
    for env_var in LOCKED_FLAG_ENV_VARS:
        monkeypatch.setenv(env_var, "true")

    policy = build_safety_policy()
    public = policy.to_public_dict()

    assert public["live_betting"] is False
    assert public["automated_wagering"] is False
    assert public["tournamental_pick_submission"] is False
    assert set(public["ignored_enable_requests"]) == set(LOCKED_FLAG_ENV_VARS)
    assert find_forbidden_output_keys(public) == ()


def test_forbidden_betting_output_keys_are_rejected():
    payload = {
        "fixture_id": "demo",
        "prediction": {
            "home_win": 0.45,
            "draw": 0.29,
            "away_win": 0.26,
            "recommended_bet": "home_win",
        },
        "audit": [{"stake_size": 10}],
    }

    findings = find_forbidden_output_keys(payload)

    assert findings == ("$.prediction.recommended_bet", "$.audit[0].stake_size")
    with pytest.raises(ValueError, match="Forbidden betting output keys present"):
        enforce_no_forbidden_output_keys(payload)


def test_market_data_roles_are_read_only_and_allowed():
    payload = {
        "market_consensus": {"home_win": 0.43, "draw": 0.30, "away_win": 0.27},
        "external_signal": {"source": "tournamental_bot_arena"},
        "paper_tracking": {"closing_probability": None},
    }

    assert set(ALLOWED_MARKET_DATA_ROLES) == {
        "market_consensus",
        "external_signal",
        "paper_tracking",
    }
    assert enforce_no_forbidden_output_keys(payload) is payload
