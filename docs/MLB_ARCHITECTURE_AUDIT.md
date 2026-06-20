# MLB Architecture Audit for Football Migration

## Scope

Reference repo: `wujoshnjr/mlb-prediction-app`.

This audit is based on files actually read through the GitHub connector:

- `README.md`
- `main.py`
- `model.py`
- `prediction.py`
- `config.py`
- `requirements.txt`
- `scripts/feature_schema.py`
- `scripts/risk_guard.py`
- `scripts/snapshot_store.py`
- `scripts/data_contract_validator.py`
- `scripts/pipeline_manifest.py`
- `scripts/promotion_gate.py`
- `scripts/calibration_report.py`
- `scripts/sample_state_builder.py`
- `scripts/baseline_comparison_report.py`
- `scripts/market_close_report.py`
- `scripts/mlb_stats_client.py`
- `scripts/odds_client.py`
- `scripts/sanitize_prediction_report.py`
- `scripts/html_report_builder.py`
- `scripts/model_artifact_status.py`

GitHub Actions workflow files were not discovered through the connector at tried paths (`.github/workflows/daily.yml`, `mlb.yml`, `main.yml`, `python-app.yml`, `update.yml`, `daily-update.yml`, `daily-prediction.yml`, `scheduled.yml`). The README describes the scheduled workflow behavior, so this audit treats that README workflow description as documented intent unless a workflow file is later found.

## Project Positioning

The MLB repo is a paper-trading research dashboard and market comparison evidence pipeline. It tracks predictions, market odds, closing-line value, data quality, model governance, sample state, market-baseline comparison, and dashboard artifacts.

It explicitly states it is not a real-money betting execution system. Live betting, production replacement, automated wagering, and user funds are expected to stay disabled.

Football migration implication: copy the governance architecture, not MLB domain assumptions.

## `main.py`

`main.py` is a self-contained FastAPI dashboard titled MLB Intelligence Cloud. It serves dashboard UI and JSON endpoints around report artifacts, snapshots, market odds, sample state, finalized games, product experience, and daily accuracy. It imports prediction generation defensively so the dashboard can still boot if prediction import fails.

Important patterns for football:

- Dashboard reads artifacts rather than triggering unsafe external behavior on every request.
- Safety copy and paper-only locks are visible in the app layer.
- Report and data paths are centralized as `Path` constants.
- Missing or invalid artifacts are handled with fallbacks.

Football equivalent: a World Cup dashboard/API layer serving source health, fixture board, prediction evidence, market consensus, and data contract status from generated artifacts.

## `model.py`

`model.py` is a unified upstream data collection layer with a stable prediction contract. It imports many optional clients, catches import failures, and records errors instead of crashing. `UnifiedSportsModel.gather_all_data()` collects schedule, statcast, retrosheet, pybaseball, sportsipy, weather, odds, pitchers, injuries, bullpen, platoon, and umpire data.

Important patterns for football:

- Optional source modules can fail without killing the whole pipeline.
- Source fetch errors are gathered into an `errors` list.
- Outputs are normalized into records.
- Odds are matched to schedule rows with audit fields and confidence.

Football equivalent: source adapters and fixture/context ingestion that return source reports, errors, warnings, normalized records, and provenance without crashing.

## `prediction.py`

`prediction.py` generates daily MLB predictions and writes `report/prediction.json`. It uses:

- `UnifiedSportsModel`
- `scripts.feature_schema`
- `scripts.risk_guard.LiveBetRiskGuard`
- optional imports for rating, simulation, park, lineup, snapshot, and market helpers
- model artifact gate status
- JSON safety helpers that remove non-finite values

Important patterns for football:

- Prediction runtime is guarded by a shared feature schema hash.
- Optional helpers fail soft.
- Model artifact eligibility is checked before active use.
- Snapshot and market stores are called from the prediction pipeline.
- Suspicious market data is tracked but must not become real execution.

Football equivalent: football prediction generation must support 1X2 and knockout `advance_result`, keep source provenance, and preserve paper-only market comparison.

## `config.py`

`config.py` defines runtime feature flags and model settings. Experimental features are default-off. Snapshot policy, pipeline version, paper-trading mode, and minimum sample thresholds are centralized.

Important patterns for football:

- Feature gates default conservative.
- Pipeline and snapshot policy are explicit.
- Clean training sample thresholds are separate from runtime prediction.
- Config blocks premature promotion.

Football equivalent: football config should centralize `PIPELINE_VERSION`, `SNAPSHOT_POLICY`, feature gates, safety flags, and sample thresholds without enabling betting behavior.

## `scripts/feature_schema.py`

This file is the single source of truth for feature order and feature governance. It separates:

- `CORE_MODEL_FEATURES`
- `DEFERRED_ZERO_MODEL_FEATURES`
- `AVAILABILITY_FLAG_FEATURES`
- `TRACKING_ONLY_FEATURES`
- `SHADOW_CANDIDATE_FEATURES`
- feature schema hash
- feature groups

Important patterns for football:

- Active model features must be explicit and stable.
- Tracking-only and shadow features cannot silently enter active training.
- Availability flags make missing-source behavior visible.

Football equivalent: `football_feature_schema.py` with football-specific core, tracking-only, availability, and shadow candidate groups.

## `scripts/risk_guard.py`

`LiveBetRiskGuard` evaluates candidate signals against market research, CLV buckets, lineup status, feature health, and critical feature validity. It is a defensive gate in the MLB project.

Important football migration warning: this concept must become a no-live-betting and paper-only safety guard, not a betting recommendation engine. Football should use this pattern to reject unsafe outputs and block live/pick submission paths.

## `scripts/snapshot_store.py`

The snapshot store is a key governance component. It documents and implements:

- forward-collected only snapshots
- pregame eligibility
- only first valid pregame snapshot per pipeline/game
- settlement writes final results only
- legacy/backfilled rows not clean training samples
- canonical snapshot columns

Football equivalent: `football_snapshot_store.py` should keep `first_seen_pregame` snapshots, support 1X2 and knockout advance fields, and prevent settlement from mutating pregame features.

## `scripts/data_contract_validator.py`

The data contract validator checks required and optional reports, missing files, JSON validity, allowed statuses, bad scalar values, and safety flags.

Important patterns for football:

- Data quality is validated after reports are generated.
- Missing or invalid reports become structured errors/warnings.
- NaN / Infinity-like values are blocked.
- Safety flags must remain false.

Football equivalent: `football_data_contract_validator.py` should validate source reports, fixture ingestion reports, snapshots, safety flags, forbidden output keys, and secret leakage.

## `scripts/pipeline_manifest.py`

The manifest inventories reports, data files, scripts, docs, site assets, and model artifacts. It records existence, hashes, JSON summaries, CSV row counts, and metadata.

Football equivalent: `football_pipeline_manifest.py` should track football reports, fixture data, snapshots, market history, weather, injuries, lineups, sample state, and dashboard artifacts.

## `scripts/sample_state_builder.py`

Sample state is the canonical place for counts and readiness: raw snapshots, valid snapshots, settled snapshots, training samples, model artifact samples, walk-forward predictions, and calibration readiness.

Football equivalent: football sample state should count pregame snapshots, settled fixtures, clean training samples, group-stage vs knockout samples, and calibration/evaluation readiness.

## Evaluation and Market Reports

Read files show:

- `scripts/baseline_comparison_report.py` compares model probabilities to baselines and market no-vig.
- `scripts/calibration_report.py` creates Brier / calibration tables and refuses to pretend missing samples are valid.
- `scripts/market_close_report.py` links snapshots with closing market odds and CLV evidence.
- `scripts/promotion_gate.py` blocks promotion based on samples, walk-forward count, Brier/logloss vs market, CLV, calibration, research quality, and data contract status.

Football equivalent: use multiclass 1X2 Brier / LogLoss / calibration, model-vs-market no-vig 1X2, low-sample `insufficient_sample`, and explicit promotion blocks.

## Source/Data Layer

`model.py`, `scripts/mlb_stats_client.py`, and `scripts/odds_client.py` show a mixed source architecture:

- Source functions return DataFrames or empty DataFrames on failures.
- Errors are appended to shared error lists.
- Odds diagnostics redact API keys.
- Market data includes quality status and suspicious-market reasons.

Football equivalent: use standardized source adapters with JSON reports and provenance. Odds/market feeds stay read-only.

## Dashboard / API Layer

`main.py` and `scripts/html_report_builder.py` provide dashboard surfaces from report artifacts. The dashboard is report-driven and safety-copy-aware.

Football equivalent: source health matrix, fixture board, prediction evidence, market consensus, and data contract status should be served from generated safe artifacts where possible.

## GitHub Actions / CI

The README documents a scheduled workflow that installs dependencies, compiles critical Python files, updates finalized results, builds sample state, trains only if enough finalized samples exist, collects context, generates prediction reports, sanitizes outputs, builds evaluation and governance reports, builds dashboard HTML, runs data contract validation, runs tests, validates health gates, uploads artifacts, and commits selected outputs.

Workflow file path was not discovered in this phase, so Phase 13 should verify actual workflow files before editing CI.

## Key Architecture Lessons for Football

- Put governance in code, not just docs.
- Reports should be JSON-safe and non-crashing.
- Missing inputs should yield skipped/warning/blocked reports.
- Feature promotion must pass through a schema and hash.
- Snapshots must preserve pregame state and settlement must not rewrite features.
- Evaluation must compare against market baselines but never become betting advice.
- Promotion requires enough clean samples and safety gates.
- Dashboard should be driven by artifacts, not fragile live external calls.
- API keys must stay in env and diagnostics must redact secrets.
