from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


FORBIDDEN_OUTPUT_KEYS = frozenset({"recommended_bet", "stake_size"})
ALLOWED_MARKET_DATA_ROLES = ("market_consensus", "external_signal", "paper_tracking")
LOCKED_FLAG_ENV_VARS = (
    "LIVE_BETTING",
    "LIVE_BETTING_ENABLED",
    "AUTOMATED_WAGERING",
    "AUTOMATED_WAGERING_ENABLED",
    "TOURNAMENTAL_ENABLE_PICK_SUBMISSION",
)
_TRUE_ENV_VALUES = frozenset({"1", "true", "yes", "y", "on", "enabled"})


@dataclass(frozen=True)
class SafetyPolicy:
    """Read-only project safety state.

    These flags are deliberately locked false. Environment variables may request an
    unsafe behavior, but this policy must not enable live betting, automated wagering,
    or Tournamental pick submission.
    """

    live_betting: bool = False
    live_betting_locked: bool = True
    automated_wagering: bool = False
    automated_wagering_locked: bool = True
    tournamental_pick_submission: bool = False
    tournamental_pick_submission_locked: bool = True
    market_data_allowed_roles: tuple[str, ...] = ALLOWED_MARKET_DATA_ROLES
    ignored_enable_requests: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "live_betting": self.live_betting,
            "live_betting_locked": self.live_betting_locked,
            "automated_wagering": self.automated_wagering,
            "automated_wagering_locked": self.automated_wagering_locked,
            "tournamental_pick_submission": self.tournamental_pick_submission,
            "tournamental_pick_submission_locked": self.tournamental_pick_submission_locked,
            "market_data_allowed_roles": list(self.market_data_allowed_roles),
            "ignored_enable_requests": list(self.ignored_enable_requests),
        }


def build_safety_policy() -> SafetyPolicy:
    return SafetyPolicy(
        ignored_enable_requests=tuple(
            env_var for env_var in LOCKED_FLAG_ENV_VARS if _env_requests_enablement(env_var)
        )
    )


def find_forbidden_output_keys(payload: Any, path: str = "$") -> tuple[str, ...]:
    findings: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{path}.{key}"
            if key in FORBIDDEN_OUTPUT_KEYS:
                findings.append(key_path)
            findings.extend(find_forbidden_output_keys(value, key_path))
    elif isinstance(payload, (list, tuple)):
        for index, value in enumerate(payload):
            findings.extend(find_forbidden_output_keys(value, f"{path}[{index}]"))

    return tuple(findings)


def enforce_no_forbidden_output_keys(payload: Any) -> Any:
    findings = find_forbidden_output_keys(payload)
    if findings:
        joined = ", ".join(findings)
        raise ValueError(f"Forbidden betting output keys present: {joined}")
    return payload


def _env_requests_enablement(name: str) -> bool:
    value = os.getenv(name)
    return str(value or "").strip().lower() in _TRUE_ENV_VALUES
