# PROJECT_CONTEXT.md

## Project Positioning

`wujoshnjr/football` is the 2026 World Cup Football Prediction project. The target state is a World Cup Intelligence Pipeline: an engineering-grade football prediction and data-fusion platform that is verifiable, traceable, testable, and safe to operate.

This project is paper-only and research-only. It must not place wagers, recommend wagers, size stakes, connect to real betting APIs, submit picks, handle user funds, or encourage live betting. Any odds or market data must remain read-only and may only support market consensus, external signals, or paper tracking.

## Repo Roles

- `wujoshnjr/mlb-prediction-app`: read-only reference repo for architecture research.
- `wujoshnjr/football`: writable implementation repo for the football migration.

The MLB repo should be used to study engineering governance patterns, not to copy baseball-specific assumptions into football.

## Migration Goal

The football project should evolve toward the MLB project's engineering governance shape:

- source registry
- source adapter standardization
- source health report
- fixture ingestion report
- source provenance
- feature schema
- snapshot store
- finalized results / settlement
- data contract validator
- pipeline manifest
- sample state
- model artifact gate
- promotion gate
- calibration / evaluation
- model vs market comparison
- paper tracking ledger
- no live betting policy
- dashboard health
- GitHub Actions / CI
- tests

## Current Architecture Direction

The repository is organized around a backend FastAPI service, a frontend Next.js app, model logic, scripts, docs, reports, and data artifacts. Future work should evolve through controlled phases:

- Control documents first.
- MLB architecture audit before migration claims.
- Football gap analysis before broad rewrites.
- Source registry before broad adapter work.
- Adapter reports before scheduled ingestion.
- Provenance before data fusion.
- Snapshot storage before model evaluation.
- Feature schema before feature promotion.
- Data contracts before dashboard expansion.
- Pytest coverage in the same phase as new adapters or services.

## Canonical Data Sources

Use these 13 canonical source keys consistently in configuration, reports, provenance, docs, tests, and API payloads:

| Source key | Intended role | Notes |
| --- | --- | --- |
| `football_data` | fixture / standing source | Read-only provider adapter. |
| `api_football` | fixture / standing source | Read-only provider adapter. |
| `worldcup_2026_api` | fixture source | World Cup focused source. |
| `openfootball_worldcup_json` | fixture / historical open data | Open data fallback and validation source. |
| `zafronix_worldcup` | fixture / context source | Read-only source, exact schema must be validated. |
| `thesportsdb_worldcup` | fixture / team metadata source | Read-only source, use provenance. |
| `statsbomb_open_data` | historical events / model research | Open data research source, not live fixture authority. |
| `open_meteo_weather` | weather source | Read-only weather context. |
| `gdelt_news` | news source | Read-only news and narrative context. |
| `fifa_ranking_source` | rankings source | Ranking features and tracking inputs. |
| `sportsdataio_worldcup` | fixture / standing / context source | Read-only provider adapter using confirmed World Cup IDs. |
| `thestatsapi_worldcup` | fixture / standing / context source | Read-only provider adapter using confirmed World Cup IDs. |
| `tournamental_bot_arena` | external benchmark / read-only signal | Not official, not primary fixtures, no pick submission. |

If user notes use the typo `tournamental_bot_arena`, normalize it to `tournamental_bot_arena` in code and docs.

## Confirmed SportsDataIO World Cup Configuration

These values may be documented as safe non-secret identifiers. API keys must still come only from environment variables.

```text
SPORTSDATAIO_BASE_URL=https://api.sportsdata.io/v4/soccer
SPORTSDATAIO_WORLD_CUP_COMPETITION_KEY=21
SPORTSDATAIO_WORLD_CUP_COMPETITION_ID=21
SPORTSDATAIO_WORLD_CUP_SEASON_ID=368
SPORTSDATAIO_WORLD_CUP_SEASON=2026
```

Expected secret variable:

```text
SPORTSDATAIO_API_KEY
```

SportsDataIO notes:

- World Cup response IDs may include `CompetitionId=21`.
- Existing adapters that look for `CompetitionKey` may temporarily accept `21`.
- New work should prefer `SPORTSDATAIO_WORLD_CUP_COMPETITION_ID`.
- Do not confuse UEFA Champions League IDs with World Cup IDs.

## Confirmed TheStatsAPI World Cup Configuration

These values may be documented as safe non-secret identifiers. API keys must still come only from environment variables.

```text
THESTATSAPI_BASE_URL=https://api.thestatsapi.com/api
THESTATSAPI_WORLD_CUP_COMPETITION_ID=comp_6107
THESTATSAPI_WORLD_CUP_SEASON_ID=sn_118868
```

Expected secret variable:

```text
THESTATSAPI_API_KEY
```

## Tournamental Bot Arena Positioning

Tournamental Bot Arena is allowed only as an external prediction benchmark, bot arena reference, and read-only odds / injuries / weather signal.

It is not:

- an official source
- a primary fixture source
- a primary score source
- a real betting source
- a betting API
- a place where this project should submit picks in phase one

Rules:

- `TOURNAMENTAL_ENABLE_PICK_SUBMISSION` must default to `false`.
- First-phase integration is read-only only.
- Allowed methods are limited to catalogue and signal reads such as `get_match_catalogue`, `get_odds`, `get_injuries`, `get_weather`, and `health_check`.
- Forbidden methods include `submit_pick`, `submit_bulk_picks`, `run_bot_swarm`, and auto-submit behavior.
- Any feature that would submit picks or automate wagering must stop for user confirmation and redesign.

## Football and MLB Architecture Mapping Direction

When borrowing patterns from the MLB prediction project, map concepts carefully instead of copying domain assumptions blindly.

| MLB-oriented concept | Football project direction |
| --- | --- |
| Game source registry | Football `SourceRegistry` covering fixture, standing, team, lineup, injury, weather, news, ranking, market, and benchmark sources. |
| Game ingestion adapters | Fixture ingestion adapters with provider-specific schema validation and JSON reports. |
| Pregame snapshot | `first_seen_pregame` fixture and feature snapshot before kickoff. |
| Finalized outcomes | Post-match fixture settlement from trusted results, never from prediction snapshots. |
| Sample state | Football sample counts split by raw snapshots, valid pregame snapshots, settled snapshots, clean training samples, and knockout support. |
| Feature groups | Football feature schema split into core model, tracking-only, availability flag, and shadow candidate features. |
| Model evaluation | Multiclass home/draw/away Brier, LogLoss, calibration, and knockout advance-result evaluation. |
| Market comparison | Read-only model-vs-market no-vig 1X2 report, not betting advice. |
| Paper tracking | Paper-only signal ledger with no stake sizing and no bet recommendation. |
| Risk guard | No-live-betting and no-automated-wagering policy. |
| Promotion gate | Sample-size, calibration, model-vs-market, data-quality, and safety gates before any production-readiness claim. |
| Dashboard health | Source health matrix, fixture board payload, evidence payload, and market consensus payload. |
| Pipeline manifest | Artifact inventory for reports, data files, snapshots, and generated dashboard outputs. |

## Football-Specific Differences

Football must not inherit MLB binary prediction behavior directly.

Football must support:

- Group-stage / normal 1X2 outcomes: `home_win`, `draw`, `away_win`.
- Knockout reporting with both `regulation_result` and `advance_result`.
- Market no-vig 1X2: `market_home_prob`, `market_draw_prob`, `market_away_prob`.
- Model 1X2: `model_home_prob`, `model_draw_prob`, `model_away_prob`.
- Pregame snapshots with `first_seen_pregame`, `kickoff_time`, `generated_at`, `source_snapshot`, `feature_version`, `model_version`, and `pipeline_version`.
- Settlement that never mutates pregame features.

Football-specific constraints:

- Draw is a first-class outcome for group-stage and league-style evaluations.
- Knockout matches may need both match-result and advance-result evaluation.
- Fixture identity must handle neutral venues, host cities, group/round, match number, and kickoff time.
- Weather, injuries, lineups, news, rankings, and market signals must retain provenance and availability flags.

## Things This Project Must Not Do

- Do not enable live betting.
- Do not enable automated wagering.
- Do not enable real-money betting.
- Do not connect to real betting APIs.
- Do not output `recommended_bet`.
- Do not output `stake_size`.
- Do not output betting advice.
- Do not store API keys or secrets in GitHub.
- Do not store API keys in test fixtures, docs, README files, generated reports, or logs.
- Do not crash on missing keys, provider failure, HTTP 401 / 403, HTTP 429, HTTP 5xx, timeout, schema mismatch, or empty responses.
- Do not treat Tournamental as official or primary fixture data.
- Do not submit Tournamental picks in phase one.
- Do not overwrite pregame prediction snapshots after kickoff.
- Do not promote new model features without schema and tests.
- Do not claim production readiness from insufficient sample sizes.
- Do not change production deploy or Render env configuration without explicit confirmation.
