# Football World Cup Prediction Platform

This repository is the 2026 World Cup Football Prediction project. The goal is an engineering-grade, verifiable, traceable, and testable football prediction and data-fusion platform.

This is not a real-money betting system. It is paper-only and research-only. It must not connect to real betting APIs, place wagers, submit picks, size stakes, or present predictions as profit guarantees. Live betting and automated wagering remain locked false.

## Safety Rules

- `live_betting_allowed` must stay `false`.
- `automated_wagering_allowed` must stay `false`.
- `real_money_betting_allowed` must stay `false`.
- Tournamental pick submission must stay locked false.
- API keys must come only from environment variables or deployment environment settings.
- API keys and secrets must never be committed to GitHub, docs, tests, logs, reports, or fixtures.
- Missing keys, API failures, HTTP 401 / 403, HTTP 429, HTTP 5xx, timeouts, schema mismatches, and empty responses must produce JSON reports instead of crashing.
- Odds and market data may be used only as `market_consensus`, `external_signal`, or `paper_tracking`.
- Every fixture, standing, prediction, weather item, news item, and market signal must preserve source provenance.

## Architecture

```text
frontend/  Next.js + React UI
backend/   FastAPI + Pydantic API layer
ml/        Football model experiments and baseline logic
scripts/   Source registry, ingestion, snapshot, evaluation, and governance tools
docs/      Product, data source, model, and evaluation documentation
report/    Generated JSON reports
data/      Local data artifacts and snapshots
```

## Current Engineering Controls

The project now includes controlled engineering layers for:

- source registry and source reports
- fixture ingestion reports
- source provenance
- pregame prediction snapshots
- feature schema governance
- data contract validation
- pipeline manifest generation
- multiclass evaluation and calibration
- model-vs-market comparison as evidence only
- model artifact status and promotion gate reports
- read-only Tournamental benchmark adapter
- safe GitHub Actions CI

## 2026 World Cup Match Center

The frontend homepage is the public-facing 2026 World Cup match center. It prioritizes user match information before engineering diagnostics:

- Hero summary with total fixture count, completed count, tomorrow count, and data completeness.
- One primary fixture request to `GET /fixtures?status=all&tz=Asia/Taipei`, then client-side grouping into tomorrow, completed, and upcoming sections.
- Tomorrow matches derived from the schedule payload, showing all matches for the next Taiwan calendar day returned by the backend.
- Completed results derived from the schedule payload, including scores, result, finalized timestamp, and source provenance.
- Full schedule from the same `GET /fixtures` payload, split into upcoming and completed sections.
- Runtime diagnostics at the bottom of the page, with cold-start messaging when Render appears slow.

`GET /fixtures/tomorrow` and `GET /fixtures/completed` remain available as product API endpoints, but the homepage does not depend on extra fixture fetches during cold starts.

If fixture data is incomplete, the homepage must show that state clearly. Demo fallback is labeled as demo fallback and is never presented as a complete official World Cup schedule.

## Fixture Cache

Build the World Cup fixture cache from configured canonical fixture providers:

```bash
python scripts/build_worldcup_fixture_cache.py
```

The script writes:

- `data/cache/fixtures_latest.json`
- `report/worldcup_fixture_cache_report.json`

Production deployments that should show real World Cup data must run the cache builder before deploy, or otherwise ensure `data/cache/fixtures_latest.json` is present in the backend runtime filesystem. Without that cache, `GET /fixtures?source=auto` may return explicit `demo_fallback` data with `cache_exists=false`; this is a visible fallback state, not official production schedule data.

Verify runtime cache status with:

```bash
curl http://localhost:8000/fixtures/cache/status
```

The cache status endpoint reports `cache_exists`, fixture counts, completeness, missing reason, cache path, generated timestamp, and source used. It must not expose API keys.

The cache builder is no-crash by design. Missing keys, provider failures, rate limits, 5xx responses, empty responses, and schema mismatches are recorded in JSON reports. A single provider failure must not crash the cache build.

Completeness rules:

- `is_complete_worldcup_schedule` is true only when the cache reaches the expected 2026 World Cup schedule count.
- Fixture counts below 48 are marked as materially incomplete.
- Fixture counts below the expected full schedule are marked incomplete with `missing_reason`.
- Completed matches preserve scores, result, finalized timestamp, and source provenance.
- Demo fallback is marked `demo_fallback_in_use` and never overwrites completed cache data.

Fixture API examples:

```bash
curl http://localhost:8000/fixtures
curl "http://localhost:8000/fixtures?status=completed&tz=Asia/Taipei"
curl http://localhost:8000/fixtures/cache/status
curl http://localhost:8000/fixtures/completed
curl http://localhost:8000/fixtures/tomorrow
curl http://localhost:8000/fixtures/today
curl http://localhost:8000/fixtures/date/2026-06-21
```

## Data Sources

Canonical sources are documented in [DATA_SOURCES.md](DATA_SOURCES.md). The approved source keys are:

```text
football_data
api_football
worldcup_2026_api
openfootball_worldcup_json
zafronix_worldcup
thesportsdb_worldcup
statsbomb_open_data
open_meteo_weather
gdelt_news
fifa_ranking_source
sportsdataio_worldcup
thestatsapi_worldcup
tournamental_bot_arena
```

SportsDataIO and TheStatsAPI World Cup identifiers are non-secret IDs and are documented in [DATA_SOURCES.md](DATA_SOURCES.md). Provider API keys remain environment-only.

## Model Scope

The football prediction target is multiclass 1X2:

- `home_win`
- `draw`
- `away_win`

Knockout matches may also track `advance_result` separately from regulation result. Model documentation is in [MODEL_CARD.md](MODEL_CARD.md), and evaluation methodology is in [docs/EVALUATION_METHOD.md](docs/EVALUATION_METHOD.md).

## Reports And Artifacts

Expected report/data artifacts include:

- `report/fixture_ingestion_report.json`
- `report/source_health_report.json`
- `report/worldcup_fixture_cache_report.json`
- `report/calibration_report.json`
- `report/model_vs_market_report.json`
- `report/promotion_gate_report.json`
- `report/data_contract_report.json`
- `report/pipeline_manifest.json`
- `data/cache/fixtures_latest.json`
- `data/prediction_snapshots.csv`
- `data/finalized_fixtures.csv`

Generated reports must be JSON-safe and contain no `NaN` or `Infinity` values.

## Backend Quick Start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Useful local endpoints:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/data-sources
curl http://localhost:8000/data-sources/context
curl http://localhost:8000/fixtures
curl http://localhost:8000/fixtures/cache/status
curl http://localhost:8000/fixtures/completed
curl http://localhost:8000/fixtures/tomorrow
curl http://localhost:8000/ingestion/fixtures
```

## Frontend Quick Start

```bash
cd frontend
npm install
npm run dev
```

Set the frontend API base URL with:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Runtime Smoke Check

Deployment setup and endpoint expectations are documented in [docs/RUNTIME_DEPLOYMENT_CHECKLIST.md](docs/RUNTIME_DEPLOYMENT_CHECKLIST.md).

Run the smoke check from the repository root after the backend has a public runtime URL:

```bash
FOOTBALL_BACKEND_URL=https://<backend-runtime-host> python scripts/runtime_smoke_check.py
```

The script checks `/health`, `/data-sources`, `/data-sources/canonical`, `/ingestion/fixtures`, and `/fixtures`. Missing `FOOTBALL_BACKEND_URL` or endpoint failures produce a JSON report instead of crashing. The check is read-only and does not call real betting APIs, submit picks, output recommended bets, or output stake sizing.

## Tests

```bash
pytest
```

Focused examples:

```bash
pytest tests/test_source_registry.py
pytest tests/test_fixture_ingestion_service.py
pytest tests/test_fixture_product_endpoints.py
pytest tests/test_frontend_match_center.py
pytest tests/test_football_evaluation.py
pytest tests/test_tournamental_bot_arena_adapter.py
pytest tests/test_runtime_smoke_check.py
```

External API tests must use mocks, fake clients, monkeypatching, or recorded safe fixtures. CI disables external providers by default and does not require API keys.
