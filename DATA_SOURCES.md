# DATA_SOURCES.md

## Source Policy

All source adapters are read-only. API keys must come from environment variables only and must never be committed to GitHub.

Adapter failures must not crash ingestion or API responses. Missing keys, provider failures, HTTP 401 / 403, HTTP 429, HTTP 5xx, timeouts, schema mismatches, and empty responses must become JSON source reports.

Every fixture, standing, prediction, weather item, news item, and market signal must preserve source provenance.

## Canonical Sources

| Key | Name | Requires key | Official | Role | Production use |
| --- | --- | --- | --- | --- | --- |
| `football_data` | football-data.org API v4 | yes | no | fixtures, scores, competitions, standings, teams | primary fixture candidate |
| `api_football` | API-Football API v3 | yes | no | fixtures, standings, lineups, events, stats, injuries | primary fixture candidate |
| `worldcup_2026_api` | World Cup 2026 public API | no | no | schedule, groups, stadiums, fallback fixtures | fixture cross-check |
| `openfootball_worldcup_json` | OpenFootball worldcup.json | no | no | static open-data fixtures/history | offline fixture seed |
| `zafronix_worldcup` | Zafronix World Cup API | yes | no | fixtures, teams, players, brackets, stadiums | fixture cross-check |
| `thesportsdb_worldcup` | TheSportsDB FIFA World Cup | no | no | metadata, events, teams, artwork | metadata enrichment |
| `statsbomb_open_data` | StatsBomb Open Data | no | no | historical events and lineups | offline training/research |
| `open_meteo_weather` | Open-Meteo Weather API | no | no | venue weather context | weather features |
| `gdelt_news` | GDELT DOC API | no | no | news and qualitative alerts | news signals |
| `fifa_ranking_source` | FIFA Men's World Ranking | no | yes | ranking and ranking points | team strength priors |
| `sportsdataio_worldcup` | SportsDataIO Soccer World Cup | yes | no | fixtures, scores, standings, lineups, stats, news | fixture/context cross-check |
| `thestatsapi_worldcup` | TheStatsAPI Football World Cup | yes | no | fixtures, groups, standings, match stats, xG | fixture/context cross-check |
| `tournamental_bot_arena` | Tournamental Bot Arena | yes | no | external benchmark and read-only odds/injuries/weather signals | external benchmark only |

## Confirmed SportsDataIO World Cup IDs

These are non-secret identifiers. The API key remains secret and must come from `SPORTSDATAIO_API_KEY`.

```text
SPORTSDATAIO_BASE_URL=https://api.sportsdata.io/v4/soccer
SPORTSDATAIO_WORLD_CUP_COMPETITION_KEY=21
SPORTSDATAIO_WORLD_CUP_COMPETITION_ID=21
SPORTSDATAIO_WORLD_CUP_SEASON_ID=368
SPORTSDATAIO_WORLD_CUP_SEASON=2026
```

Notes:

- World Cup responses may include `CompetitionId=21`.
- Adapters that still expect `CompetitionKey` may temporarily accept `21`.
- New work should prefer `SPORTSDATAIO_WORLD_CUP_COMPETITION_ID`.
- Do not confuse UEFA Champions League IDs with World Cup IDs.

## Confirmed TheStatsAPI World Cup IDs

These are non-secret identifiers. The API key remains secret and must come from `THESTATSAPI_KEY`.

```text
THESTATSAPI_BASE_URL=https://api.thestatsapi.com/api
THESTATSAPI_WORLD_CUP_COMPETITION_ID=comp_6107
THESTATSAPI_WORLD_CUP_SEASON_ID=sn_118868
```

## Tournamental Bot Arena

Tournamental Bot Arena is not an official source, not a primary fixture source, not a primary score source, and not a betting API.

Allowed first-phase use:

- `get_match_catalogue`
- `get_odds`
- `get_injuries`
- `get_weather`
- `health_check`

Forbidden behavior:

- pick submission
- bulk pick submission
- bot swarm execution
- automated wagering
- real-money betting

`TOURNAMENTAL_ENABLE_PICK_SUBMISSION` must default to `false` and is ignored by the read-only adapter if set true.

## Market Data Rules

Odds and market data can appear only as:

- `market_consensus`
- `external_signal`
- `paper_tracking`

Market data must not become betting advice or stake sizing. It can be used for no-vig 1X2 comparison, CLV-style diagnostics, market movement evidence, and calibration analysis.

## Source Report Standard

Every adapter should emit a JSON report with at least:

```json
{
  "source": {"key": "source_key"},
  "attempted": false,
  "success": false,
  "status": "missing_credentials",
  "record_count": 0,
  "error": null,
  "missing_env": [],
  "checked_at": "2026-06-20T00:00:00Z"
}
```

Supported statuses include:

```text
ok
disabled
missing_credentials
missing_world_cup_ids
missing_world_cup_competition_key
unauthorized_or_forbidden
rate_limited
upstream_error
empty_response
schema_mismatch
timeout
```

## Provenance Fields

Records should include source provenance containing:

- source key
- source role
- fetched or observed timestamp
- endpoint or artifact path when available
- provider fixture id when available
- transformation or normalization step when available
- read-only flag for external benchmark sources

Provenance must be retained through ingestion, fusion, prediction, evaluation, dashboard payloads, and reports.
