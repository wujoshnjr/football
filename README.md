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
- `report/calibration_report.json`
- `report/model_vs_market_report.json`
- `report/promotion_gate_report.json`
- `report/data_contract_report.json`
- `report/pipeline_manifest.json`
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
pytest tests/test_football_evaluation.py
pytest tests/test_tournamental_bot_arena_adapter.py
pytest tests/test_runtime_smoke_check.py
```

External API tests must use mocks, fake clients, monkeypatching, or recorded safe fixtures. CI disables external providers by default and does not require API keys.
