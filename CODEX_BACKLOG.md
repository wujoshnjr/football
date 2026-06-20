# CODEX_BACKLOG.md

## Execution Policy

This backlog is executed phase by phase. Codex should proceed automatically unless a stop condition from `AGENTS.md` is met.

Global rules:

- Read relevant files before changing code.
- Keep each phase scoped to its listed files unless a small supporting file is clearly required.
- Do not modify prediction model behavior unless the phase explicitly requires it.
- Do not modify Render environment variables or production deploy settings without confirmation.
- Do not connect real betting APIs or add any write path for wagering.
- Do not automatically merge to `main`.
- Run the most relevant tests when the local environment supports it.
- If tests fail, attempt up to three focused repair cycles, then stop and log the failure.
- Update this file and `CODEX_EXECUTION_LOG.md` after each phase.

## Phase 0: Control Documents

Status: complete

Files:

- [x] `AGENTS.md`
- [x] `PROJECT_CONTEXT.md`
- [x] `CODEX_BACKLOG.md`
- [x] `CODEX_EXECUTION_LOG.md`

Acceptance criteria:

- Project goal and safety rules are documented.
- API key / env rules are documented.
- Missing-data and provider-failure no-crash rules are documented.
- Adapter JSON report standard is documented.
- Source provenance rules are documented.
- Pytest / testing requirements are documented.
- Live betting locked and no real betting policy are documented.
- Codex phase execution, testing, commit, and log-update rules are documented.

## Phase 1: MLB Architecture Research

Status: complete

Read-only repo:

- `wujoshnjr/mlb-prediction-app`

Created in football repo:

- [x] `docs/MLB_ARCHITECTURE_AUDIT.md`
- [x] `docs/MLB_FILE_PURPOSE_MAP.md`
- [x] `docs/MLB_PIPELINE_FLOW.md`
- [x] `docs/MLB_TO_FOOTBALL_MIGRATION_PLAN.md`

Acceptance criteria:

- Do not guess MLB architecture; read real repo files.
- Audit main app, model, prediction, config, scripts, tests, docs, report, data, site, GitHub Actions, dashboard/API, prediction layer, model layer, data source layer, feature engineering, snapshot store, paper/shadow tracking, risk guard, data contract, pipeline manifest, calibration/evaluation, promotion gate, and safety policy.
- File purpose map includes path, category, purpose, inputs, outputs, functions/classes, dependencies, downstream users, reusability, football equivalent, priority, and notes.
- Pipeline flow documents collection, features, prediction, snapshot, settlement, calibration, CLV/model-vs-market, risk guard, promotion gate, reports, dashboard, data contract, and CI order.
- Migration plan maps MLB components to football equivalents and test requirements.

## Phase 2: Football Architecture Gap Analysis

Status: complete

Created:

- [x] `docs/FOOTBALL_ARCHITECTURE_GAP_ANALYSIS.md`

Acceptance criteria:

- Current football file-purpose table exists.
- Existing MLB-like architecture is identified.
- Missing MLB-like architecture is identified.
- Duplicated or confusing areas are identified.
- Keep/refactor/add recommendations are included.
- Test gaps are listed.
- Adapter JSON report gaps are listed.
- API no-crash risks are listed.
- Source provenance gaps are listed.
- No-live-betting policy gaps are listed.
- P0/P1/P2/P3 implementation order is included.

## Phase 3: SourceRegistry and SourceReport Schema

Status: complete

Created or updated:

- [x] `scripts/source_registry.py`
- [x] `scripts/source_report_schema.py`
- [x] `tests/test_source_registry.py`

Acceptance criteria:

- Registry contains exactly the 13 canonical sources.
- Each source includes `key`, `name`, `requires_key`, `official`, `role`, `production_use`, `priority`, `env_vars`, `enabled_env`, `configured`, and `missing_reason`.
- SourceReport schema includes `source`, `attempted`, `success`, `status`, `record_count`, `error`, `missing_env`, and `checked_at`.
- Supported statuses include `ok`, `disabled`, `missing_credentials`, `missing_world_cup_ids`, `missing_world_cup_competition_key`, `unauthorized_or_forbidden`, `rate_limited`, `upstream_error`, `empty_response`, `schema_mismatch`, and `timeout`.
- Missing env does not crash.
- SportsDataIO and TheStatsAPI World Cup IDs are readable from env/default config.
- Tournamental pick submission defaults false.
- Pytest coverage exists.

## Phase 4: FixtureIngestionService

Status: pending

Create or update:

- [ ] `scripts/fixture_ingestion_service.py`
- [ ] `report/fixture_ingestion_report.json` or generation logic
- [ ] `tests/test_fixture_ingestion_service.py`

Phase-one fixture sources:

- `football_data`
- `api_football`
- `worldcup_2026_api`
- `openfootball_worldcup_json`
- `sportsdataio_worldcup`
- `thestatsapi_worldcup`

Acceptance criteria:

- Service outputs `run_id`, `checked_at`, source reports, merged fixture count, teams count, groups count, errors, and warnings.
- Every fixture supports source provenance.
- Missing keys do not crash.
- Empty API data does not crash.
- Report schema is valid.
- SportsDataIO IDs are correct.
- TheStatsAPI IDs are correct.
- Tests use mocks/fakes and do not call real external APIs.

## Phase 5: API Endpoints

Status: pending

Create or update FastAPI endpoints:

- [ ] `/data-sources`
- [ ] `/data-sources/context`
- [ ] `/ingestion/fixtures`
- [ ] `/fixtures`
- [ ] `/fixtures/{fixture_id}`

Acceptance criteria:

- Existing endpoints are not broken.
- Missing env does not crash.
- Responses do not include API keys or secrets.
- Errors are standardized.
- Source report format is correct.
- Pytest coverage exists.

## Phase 6: Football Feature Schema

Status: pending

Create:

- [ ] `scripts/football_feature_schema.py`
- [ ] `tests/test_football_feature_schema.py`

Acceptance criteria:

- `CORE_MODEL_FEATURES` includes conservative first-version football features.
- `TRACKING_ONLY_FEATURES` includes lineups, injuries, xG, market no-vig 1X2, weather, news, and Tournamental market-gap candidates.
- `AVAILABILITY_FLAG_FEATURES` includes fixture, odds, lineup, injury, suspension, weather, FIFA ranking, xG, and news availability flags.
- `SHADOW_CANDIDATE_FEATURES` is defined.
- Feature promotion must pass through schema and cannot silently enter the active model.
- Pytest coverage exists.

## Phase 7: Snapshot Store

Status: pending

Create:

- [ ] `scripts/football_snapshot_store.py`
- [ ] `tests/test_football_snapshot_store.py`

Artifacts:

- `prediction_snapshots.csv`
- `finalized_fixtures.csv`

Acceptance criteria:

- Only pre-kickoff snapshots are saved as clean pregame snapshots.
- Each fixture/pipeline version keeps only `first_seen_pregame`.
- Settlement writes post-match results only.
- Settlement never mutates pregame features.
- Backfilled rows are not treated as clean forward-collected samples.
- Football 3-way prediction is supported.
- Knockout `advance_result` is supported.
- Pytest coverage exists.

## Phase 8: Data Contract Validator

Status: pending

Create:

- [ ] `scripts/football_data_contract_validator.py`
- [ ] `tests/test_football_data_contract_validator.py`

Acceptance criteria:

- Required report JSON files are checked.
- JSON contains no NaN or Infinity.
- Required fields are checked.
- Source report schema is validated.
- `live_betting_allowed`, `automated_wagering_allowed`, and `real_money_betting_allowed` cannot be true.
- `recommended_bet` and `stake_size` cannot appear.
- API keys cannot appear in tracked files.
- Prediction snapshots cannot contain leaked forbidden fields.
- Pytest coverage exists.

## Phase 9: Pipeline Manifest

Status: pending

Create:

- [ ] `scripts/football_pipeline_manifest.py`
- [ ] `tests/test_football_pipeline_manifest.py`

Track artifacts:

- `report/prediction.json`
- `report/fixture_ingestion_report.json`
- `report/source_health_report.json`
- `report/baseline_comparison_report.json`
- `report/calibration_report.json`
- `report/promotion_gate_report.json`
- `report/data_contract_report.json`
- `report/pipeline_manifest.json`
- `data/fixtures.csv`
- `data/finalized_fixtures.csv`
- `data/prediction_snapshots.csv`
- `data/market_odds_history.csv`
- `data/team_strength_context.csv`
- `data/weather_context.csv`
- `data/injury_context.csv`
- `data/lineup_context.csv`
- `data/sample_state.json`

Acceptance criteria:

- Each artifact records path, exists, size, sha256, csv row count when applicable, json top-level keys when applicable, and updated_at.
- Missing artifacts do not crash manifest generation.
- Pytest coverage exists.

## Phase 10: Evaluation / Calibration

Status: pending

Create:

- [ ] `scripts/football_calibration_report.py`
- [ ] `scripts/football_model_vs_market_report.py`
- [ ] `tests/test_football_evaluation.py`

Acceptance criteria:

- Multiclass Brier score is supported.
- Multiclass LogLoss is supported.
- Home/draw/away calibration is supported.
- Model vs market no-vig 1X2 comparison is supported.
- Group-stage vs knockout slices are supported.
- Favorite vs underdog slices are supported.
- CLV / market movement is supported as evidence, not betting advice.
- Reports include sample_count.
- Low sample count reports `insufficient_sample` instead of pretending the model passed.
- Pytest coverage exists.

## Phase 11: Promotion Gate / Model Artifact Gate

Status: pending

Create:

- [ ] `scripts/football_promotion_gate.py`
- [ ] `scripts/football_model_artifact_status.py`
- [ ] `tests/test_football_promotion_gate.py`

Acceptance criteria:

- `clean_train_samples < 300` blocks production model claims.
- `settled_predictions < 500` blocks formal calibration conclusions.
- `production_samples < 1000` blocks `production_ready`.
- `feature_schema_hash` must match.
- Missing artifact falls back to `manual_baseline`.
- Missing model does not crash.
- `model_source` is one of `manual_baseline`, `trained_artifact`, or `shadow_model`.
- Pytest coverage exists.

## Phase 12: Tournamental Read-Only Adapter

Status: pending

Create:

- [ ] `scripts/adapters/tournamental_bot_arena_adapter.py`
- [ ] `tests/test_tournamental_bot_arena_adapter.py`

Read-only methods:

- `get_match_catalogue`
- `get_odds`
- `get_injuries`
- `get_weather`
- `health_check`

Forbidden methods / behavior:

- `submit_pick`
- `submit_bulk_picks`
- `run_bot_swarm`
- auto-submit picks

Acceptance criteria:

- Missing key does not crash.
- Pick submission defaults false.
- Odds are labeled only as `external_signal` or `market_consensus`.
- No `recommended_bet` appears.
- No `stake_size` appears.
- Pytest coverage exists.

## Phase 13: GitHub Actions / CI

Status: pending

Create or update workflow carefully.

Acceptance criteria:

- Installs dependencies.
- Compiles critical files.
- Runs pytest.
- Runs data contract validator if available.
- Runs pipeline manifest if available.
- Does not deploy.
- Does not require API keys.
- External API tests are skipped by default.
- Does not trigger real API high-frequency calls.
- Does not trigger betting, pick submission, or production deployment.

## Phase 14: README / Model Card / Data Sources / Evaluation Docs

Status: pending

Create or update:

- [ ] `README.md`
- [ ] `MODEL_CARD.md`
- [ ] `DATA_SOURCES.md`
- [ ] `docs/EVALUATION_METHOD.md`

Acceptance criteria:

- Paper-only / research-only status is clear.
- Not a betting system.
- No live betting.
- Source list and source roles are documented.
- Model limitations are documented.
- Sample count requirements are documented.
- Evaluation metrics are documented.
- No guarantee of profit.
- Odds are market consensus only.
- Data quality limitations are documented.
- API failure behavior is documented.

## Phase 15: Final Integration Check

Status: pending

Create:

- [ ] `docs/FOOTBALL_MLB_MIGRATION_COMPLETION_REPORT.md`

Acceptance criteria:

- Completed phases are listed.
- Unfinished phases are listed.
- Modified files table is included.
- Added files table is included.
- Test summary is included.
- Remaining risks are listed.
- Next steps are listed.
- Safety rule gaps are assessed.
- API key leak risk is assessed.
- Production deploy risk is assessed.
- Final checks run: pytest, data contract validator if available, pipeline manifest if available.

## Current Next Phase

Phase 4: FixtureIngestionService.
