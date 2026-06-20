from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}

DEFAULT_ENV_VALUES: dict[str, str] = {
    "API_FOOTBALL_BASE_URL": "https://v3.football.api-sports.io",
    "FOOTBALL_DATA_BASE_URL": "https://api.football-data.org/v4",
    "OPENFOOTBALL_WORLDCUP_JSON_URL": "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
    "STATSBOMB_OPEN_DATA_BASE_URL": "https://raw.githubusercontent.com/statsbomb/open-data/master/data",
    "OPEN_METEO_BASE_URL": "https://api.open-meteo.com/v1",
    "GDELT_DOC_BASE_URL": "https://api.gdeltproject.org/api/v2/doc/doc",
    "FIFA_RANKING_URL": "https://inside.fifa.com/fifa-world-ranking/men",
    "SPORTSDATAIO_BASE_URL": "https://api.sportsdata.io/v4/soccer",
    "SPORTSDATAIO_WORLD_CUP_COMPETITION_KEY": "21",
    "SPORTSDATAIO_WORLD_CUP_COMPETITION_ID": "21",
    "SPORTSDATAIO_WORLD_CUP_SEASON_ID": "368",
    "SPORTSDATAIO_WORLD_CUP_SEASON": "2026",
    "THESTATSAPI_BASE_URL": "https://api.thestatsapi.com/api",
    "THESTATSAPI_WORLD_CUP_COMPETITION_ID": "comp_6107",
    "THESTATSAPI_WORLD_CUP_SEASON_ID": "sn_118868",
    "THESPORTSDB_BASE_URL": "https://www.thesportsdb.com/api/v1/json",
    "THESPORTSDB_API_KEY": "123",
    "THESPORTSDB_WORLD_CUP_LEAGUE_ID": "4429",
    "THESPORTSDB_WORLD_CUP_SEASON": "2026",
    "TOURNAMENTAL_TOURNAMENT_ID": "fifa-wc-2026",
    "TOURNAMENTAL_ENABLE_READ_ONLY_FEEDS": "true",
    "TOURNAMENTAL_ENABLE_PICK_SUBMISSION": "false",
}


@dataclass(frozen=True)
class EnvRequirement:
    """One required env value, optionally allowing legacy aliases."""

    name: str
    aliases: tuple[str, ...] = ()

    @property
    def choices(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    requires_key: bool
    official: bool
    role: str
    production_use: str
    priority: int
    env_vars: tuple[str, ...] = ()
    required_env: tuple[EnvRequirement, ...] = ()
    enabled_env: str | None = None
    default_enabled: bool = False
    world_cup_id_env: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceStatus:
    key: str
    name: str
    requires_key: bool
    official: bool
    role: str
    production_use: str
    priority: int
    env_vars: tuple[str, ...]
    enabled_env: str | None
    enabled: bool
    configured: bool
    missing_env: tuple[str, ...]
    missing_reason: str | None
    world_cup_ids: Mapping[str, str]
    safety_flags: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["env_vars"] = list(self.env_vars)
        payload["missing_env"] = list(self.missing_env)
        payload["warnings"] = list(self.warnings)
        return payload


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        key="football_data",
        name="football-data.org API v4",
        requires_key=True,
        official=False,
        role="Primary fixture, score, competition, standing, and team reference candidate.",
        production_use="primary_fixture_source",
        priority=1,
        env_vars=("FOOTBALL_DATA_BASE_URL", "FOOTBALL_DATA_TOKEN", "FOOTBALL_DATA_ENABLED"),
        required_env=(EnvRequirement("FOOTBALL_DATA_TOKEN"),),
        enabled_env="FOOTBALL_DATA_ENABLED",
        default_enabled=True,
    ),
    SourceDefinition(
        key="api_football",
        name="API-Football API v3",
        requires_key=True,
        official=False,
        role="Premium fixture, score, standing, lineup, event, injury, and statistics source candidate.",
        production_use="primary_fixture_source",
        priority=2,
        env_vars=("API_FOOTBALL_BASE_URL", "API_FOOTBALL_KEY", "API_FOOTBALL_ENABLED"),
        required_env=(EnvRequirement("API_FOOTBALL_KEY"),),
        enabled_env="API_FOOTBALL_ENABLED",
        default_enabled=True,
    ),
    SourceDefinition(
        key="worldcup_2026_api",
        name="World Cup 2026 public API",
        requires_key=False,
        official=False,
        role="No-key public 2026 World Cup schedule, group, stadium, and fallback fixture endpoint.",
        production_use="fixture_cross_check",
        priority=3,
        env_vars=("WORLD_CUP_2026_API_BASE_URL", "WORLD_CUP_2026_API_ENABLED"),
        required_env=(EnvRequirement("WORLD_CUP_2026_API_BASE_URL", aliases=("WORLDCUP_2026_PUBLIC_BASE_URL",)),),
        enabled_env="WORLD_CUP_2026_API_ENABLED",
        default_enabled=False,
    ),
    SourceDefinition(
        key="openfootball_worldcup_json",
        name="OpenFootball worldcup.json",
        requires_key=False,
        official=False,
        role="Static open-data World Cup schedule/history source for fallback fixtures and regression tests.",
        production_use="offline_fixture_seed",
        priority=4,
        env_vars=("OPENFOOTBALL_WORLDCUP_JSON_URL", "OPENFOOTBALL_WORLDCUP_JSON_ENABLED"),
        enabled_env="OPENFOOTBALL_WORLDCUP_JSON_ENABLED",
        default_enabled=True,
    ),
    SourceDefinition(
        key="zafronix_worldcup",
        name="Zafronix World Cup API",
        requires_key=True,
        official=False,
        role="World Cup fixtures, teams, players, brackets, stadiums, and standings fallback candidate.",
        production_use="fixture_cross_check",
        priority=5,
        env_vars=("ZAFRONIX_WORLD_CUP_BASE_URL", "ZAFRONIX_WORLD_CUP_KEY", "ZAFRONIX_WORLD_CUP_ENABLED"),
        required_env=(
            EnvRequirement("ZAFRONIX_WORLD_CUP_BASE_URL", aliases=("ZAFRONIX_WORLDCUP_BASE_URL",)),
            EnvRequirement("ZAFRONIX_WORLD_CUP_KEY", aliases=("ZAFRONIX_WORLDCUP_KEY", "ZAFRONIX_WORLD_CUP_API_KEY")),
        ),
        enabled_env="ZAFRONIX_WORLD_CUP_ENABLED",
        default_enabled=False,
    ),
    SourceDefinition(
        key="thesportsdb_worldcup",
        name="TheSportsDB FIFA World Cup",
        requires_key=False,
        official=False,
        role="Metadata, event, team badge, artwork, and fixture/result cross-check source.",
        production_use="metadata_enrichment",
        priority=6,
        env_vars=(
            "THESPORTSDB_BASE_URL",
            "THESPORTSDB_API_KEY",
            "THESPORTSDB_WORLD_CUP_LEAGUE_ID",
            "THESPORTSDB_WORLD_CUP_SEASON",
            "THESPORTSDB_ENABLED",
        ),
        enabled_env="THESPORTSDB_ENABLED",
        default_enabled=False,
        world_cup_id_env={"league_id": "THESPORTSDB_WORLD_CUP_LEAGUE_ID", "season": "THESPORTSDB_WORLD_CUP_SEASON"},
    ),
    SourceDefinition(
        key="statsbomb_open_data",
        name="StatsBomb Open Data",
        requires_key=False,
        official=False,
        role="Open event, lineup, match, competition, and 360 data for offline training and feature research.",
        production_use="offline_training_data",
        priority=7,
        env_vars=("STATSBOMB_OPEN_DATA_BASE_URL", "STATSBOMB_OPEN_DATA_ENABLED"),
        enabled_env="STATSBOMB_OPEN_DATA_ENABLED",
        default_enabled=True,
    ),
    SourceDefinition(
        key="open_meteo_weather",
        name="Open-Meteo Weather API",
        requires_key=False,
        official=False,
        role="Venue weather, historical weather, temperature, humidity, precipitation, and wind feature source.",
        production_use="weather_feature_source",
        priority=8,
        env_vars=("OPEN_METEO_BASE_URL", "OPEN_METEO_ARCHIVE_BASE_URL", "OPEN_METEO_ENABLED"),
        enabled_env="OPEN_METEO_ENABLED",
        default_enabled=False,
    ),
    SourceDefinition(
        key="gdelt_news",
        name="GDELT DOC API",
        requires_key=False,
        official=False,
        role="News, injury, suspension, travel, coach-comment, and qualitative alert monitoring source.",
        production_use="news_signal_source",
        priority=9,
        env_vars=("GDELT_DOC_BASE_URL", "GDELT_ENABLED"),
        enabled_env="GDELT_ENABLED",
        default_enabled=False,
    ),
    SourceDefinition(
        key="fifa_ranking_source",
        name="FIFA Men's World Ranking",
        requires_key=False,
        official=True,
        role="Official public team ranking and ranking-points baseline for national-team strength priors.",
        production_use="team_strength_source",
        priority=10,
        env_vars=("FIFA_RANKING_URL", "FIFA_RANKING_ENABLED"),
        enabled_env="FIFA_RANKING_ENABLED",
        default_enabled=False,
    ),
    SourceDefinition(
        key="sportsdataio_worldcup",
        name="SportsDataIO Soccer - FIFA World Cup 2026",
        requires_key=True,
        official=False,
        role="Paid/trial provider candidate for schedules, scores, standings, lineups, stats, news, and optional market signals.",
        production_use="fixture_cross_check",
        priority=11,
        env_vars=(
            "SPORTSDATAIO_BASE_URL",
            "SPORTSDATAIO_API_KEY",
            "SPORTSDATAIO_WORLD_CUP_COMPETITION_KEY",
            "SPORTSDATAIO_WORLD_CUP_COMPETITION_ID",
            "SPORTSDATAIO_WORLD_CUP_SEASON_ID",
            "SPORTSDATAIO_WORLD_CUP_SEASON",
            "SPORTSDATAIO_ENABLED",
        ),
        required_env=(EnvRequirement("SPORTSDATAIO_API_KEY"),),
        enabled_env="SPORTSDATAIO_ENABLED",
        default_enabled=False,
        world_cup_id_env={
            "competition_key": "SPORTSDATAIO_WORLD_CUP_COMPETITION_KEY",
            "competition_id": "SPORTSDATAIO_WORLD_CUP_COMPETITION_ID",
            "season_id": "SPORTSDATAIO_WORLD_CUP_SEASON_ID",
            "season": "SPORTSDATAIO_WORLD_CUP_SEASON",
        },
    ),
    SourceDefinition(
        key="thestatsapi_worldcup",
        name="TheStatsAPI Football - World Cup 2026",
        requires_key=True,
        official=False,
        role="Trial/paid provider candidate for fixtures, groups, standings, match stats, xG, player stats, and historical context.",
        production_use="fixture_cross_check",
        priority=12,
        env_vars=(
            "THESTATSAPI_BASE_URL",
            "THESTATSAPI_KEY",
            "THESTATSAPI_WORLD_CUP_COMPETITION_ID",
            "THESTATSAPI_WORLD_CUP_SEASON_ID",
            "THESTATSAPI_ENABLED",
        ),
        required_env=(EnvRequirement("THESTATSAPI_KEY"),),
        enabled_env="THESTATSAPI_ENABLED",
        default_enabled=False,
        world_cup_id_env={
            "competition_id": "THESTATSAPI_WORLD_CUP_COMPETITION_ID",
            "season_id": "THESTATSAPI_WORLD_CUP_SEASON_ID",
        },
    ),
    SourceDefinition(
        key="tournamental_bot_arena",
        name="Tournamental Bot Arena",
        requires_key=True,
        official=False,
        role="Read-only external prediction benchmark, bot arena, odds, injury, and weather signal source.",
        production_use="external_prediction_benchmark_read_only",
        priority=13,
        env_vars=(
            "TOURNAMENTAL_BASE_URL",
            "TOURNAMENTAL_API_KEY",
            "TOURNAMENTAL_TOURNAMENT_ID",
            "TOURNAMENTAL_ENABLED",
            "TOURNAMENTAL_ENABLE_READ_ONLY_FEEDS",
            "TOURNAMENTAL_ENABLE_PICK_SUBMISSION",
        ),
        required_env=(EnvRequirement("TOURNAMENTAL_BASE_URL"), EnvRequirement("TOURNAMENTAL_API_KEY")),
        enabled_env="TOURNAMENTAL_ENABLED",
        default_enabled=False,
        world_cup_id_env={"tournament_id": "TOURNAMENTAL_TOURNAMENT_ID"},
    ),
)

CANONICAL_SOURCE_KEYS: tuple[str, ...] = tuple(source.key for source in SOURCE_DEFINITIONS)


def list_sources(environ: Mapping[str, str] | None = None) -> list[dict[str, Any]]:
    env = environ if environ is not None else os.environ
    return [definition_to_status(definition, env).to_dict() for definition in SOURCE_DEFINITIONS]


def get_source_status(key: str, environ: Mapping[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    for definition in SOURCE_DEFINITIONS:
        if definition.key == key:
            return definition_to_status(definition, env).to_dict()
    raise KeyError(f"unknown source key: {key}")


def definition_to_status(definition: SourceDefinition, environ: Mapping[str, str]) -> SourceStatus:
    enabled = bool_from_env(environ, definition.enabled_env, definition.default_enabled)
    missing_env = tuple(requirement.name for requirement in definition.required_env if not lookup_any(environ, requirement.choices))
    configured = not missing_env
    missing_reason = build_missing_reason(enabled=enabled, configured=configured, missing_env=missing_env)
    world_cup_ids = resolve_world_cup_ids(definition, environ)
    safety_flags, warnings = source_safety_flags(definition, environ)

    return SourceStatus(
        key=definition.key,
        name=definition.name,
        requires_key=definition.requires_key,
        official=definition.official,
        role=definition.role,
        production_use=definition.production_use,
        priority=definition.priority,
        env_vars=definition.env_vars,
        enabled_env=definition.enabled_env,
        enabled=enabled,
        configured=configured,
        missing_env=missing_env,
        missing_reason=missing_reason,
        world_cup_ids=world_cup_ids,
        safety_flags=safety_flags,
        warnings=warnings,
    )


def build_missing_reason(*, enabled: bool, configured: bool, missing_env: tuple[str, ...]) -> str | None:
    if not enabled and missing_env:
        return f"disabled; missing_env: {', '.join(missing_env)}"
    if not enabled:
        return "disabled"
    if not configured:
        return f"missing_env: {', '.join(missing_env)}"
    return None


def resolve_world_cup_ids(definition: SourceDefinition, environ: Mapping[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for key, env_name in definition.world_cup_id_env.items():
        value = env_value(environ, env_name)
        if value:
            resolved[key] = value
    return resolved


def source_safety_flags(definition: SourceDefinition, environ: Mapping[str, str]) -> tuple[dict[str, Any], tuple[str, ...]]:
    if definition.key != "tournamental_bot_arena":
        return {}, ()

    requested = bool_from_env(environ, "TOURNAMENTAL_ENABLE_PICK_SUBMISSION", False)
    flags = {
        "pick_submission_requested": requested,
        "pick_submission_effective": False,
        "pick_submission_locked": True,
        "read_only_only": True,
    }
    warnings = ()
    if requested:
        warnings = ("TOURNAMENTAL_ENABLE_PICK_SUBMISSION is ignored because pick submission is locked false.",)
    return flags, warnings


def bool_from_env(environ: Mapping[str, str], name: str | None, default: bool) -> bool:
    if not name:
        return default
    value = env_value(environ, name)
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default


def lookup_any(environ: Mapping[str, str], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = env_value(environ, name)
        if value:
            return value
    return None


def env_value(environ: Mapping[str, str], name: str) -> str | None:
    raw = environ.get(name)
    if raw is not None and str(raw).strip() != "":
        return str(raw)
    default = DEFAULT_ENV_VALUES.get(name)
    return default if default and str(default).strip() else None
