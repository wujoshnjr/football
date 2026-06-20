# CODEX_BACKLOG.md

## Execution Policy

This backlog is executed one controlled round at a time.

Rules for each round:

- Pick the highest-priority unfinished task with the smallest safe scope.
- Modify at most 3 to 6 files unless the user explicitly approves a larger refactor.
- Do not modify prediction model behavior unless the task explicitly requires it.
- Do not modify Render environment variables or production deploy settings without confirmation.
- Do not connect real betting APIs or add any write path for wagering.
- Do not automatically merge to `main`.
- Stop after each round and report changed files, added files, test commands, test results, skipped-test reasons, and the recommended next task.

## P0: Engineering Rules and Safety

- [x] Confirm `AGENTS.md` is complete for current project guardrails.
- [x] Create no-live-betting policy test.
- [ ] Create API-key-must-not-be-written-to-repo check.
- [ ] Create source report schema.

Acceptance criteria:

- Live betting defaults locked and false.
- Automated wagering defaults false.
- Safety policy tests fail if forbidden betting outputs or write paths appear.
- Source report schema validates adapter JSON reports.
- API keys are read only from environment variables.

## P1: Source Registry

- [ ] Create `SourceRegistry`.
- [ ] Include all 13 canonical sources.
- [ ] Each source includes `key`, `name`, `requires_key`, `official`, `role`, `priority`, `env_vars`, `enabled`, `configured`, and `missing_reason`.
- [ ] Add `/data-sources` endpoint.
- [ ] Add `/data-sources/context` endpoint.
- [ ] Add pytest coverage.

Acceptance criteria:

- Missing keys do not crash registry construction.
- Every source exposes configured and missing-reason state.
- Tournamental is read-only, non-official, non-primary fixture source.
- SportsDataIO and TheStatsAPI IDs are represented as non-secret config values.

## P2: Fixture Ingestion

- [ ] Create `FixtureIngestionService`.
- [ ] Phase one sources: `football_data`, `worldcup_2026_api`, `openfootball_worldcup_json`, `api_football`, `sportsdataio_worldcup`, `thestatsapi_worldcup`.
- [ ] Ensure all API failures are handled without crashing.
- [ ] Output `fixture_ingestion_report.json`.
- [ ] Preserve source provenance.
- [ ] Add `/ingestion/fixtures` endpoint.
- [ ] Add pytest coverage.

Acceptance criteria:

- Missing key, HTTP 429, HTTP 5xx, schema mismatch, and empty response produce JSON reports.
- Fixture records include provenance.
- Partial provider failure produces `partial` or `skipped`, not uncaught exceptions.

## P3: Snapshot Store

- [ ] Create `football_snapshot_store.py`.
- [ ] Save only pre-kickoff `first_seen_pregame` snapshots.
- [ ] Settlement writes only post-match results.
- [ ] Settlement must not mutate pregame features.
- [ ] Create `prediction_snapshots.csv`.
- [ ] Add pytest coverage.

Acceptance criteria:

- Pregame snapshots are append-only.
- Settlement cannot rewrite feature columns.
- Snapshot rows retain fixture ID, model version, timestamp, and provenance references.

## P4: Feature Schema

- [ ] Create `football_feature_schema.py`.
- [ ] Define `CORE_MODEL_FEATURES`.
- [ ] Define `TRACKING_ONLY_FEATURES`.
- [ ] Define `AVAILABILITY_FLAG_FEATURES`.
- [ ] Define `SHADOW_CANDIDATE_FEATURES`.
- [ ] Require any feature promotion to pass through schema.
- [ ] Add pytest coverage.

Acceptance criteria:

- Features outside the schema are rejected or flagged.
- Tracking-only and shadow features cannot silently enter core model inputs.
- Availability flags exist for optional sources.

## P5: Data Contract / Pipeline Manifest

- [ ] Create `football_data_contract_validator.py`.
- [ ] Create `football_pipeline_manifest.py`.
- [ ] Check JSON contains no NaN or Infinity.
- [ ] Check safety flags.
- [ ] Check required reports.
- [ ] Add pytest coverage.

Acceptance criteria:

- Pipeline validation fails closed on invalid JSON values.
- Required ingestion reports are detected.
- Safety flags must keep live betting locked and automated wagering false.

## P6: Model Evaluation

- [ ] Create multiclass Brier score support.
- [ ] Create multiclass LogLoss support.
- [ ] Create calibration report.
- [ ] Support `home_win`, `draw`, and `away_win`.
- [ ] Add knockout-specific `advance_result` support.
- [ ] Create model-vs-market report.
- [ ] Add pytest coverage.

Acceptance criteria:

- Draw is evaluated as a first-class class.
- Knockout advance-result reporting is separate from regulation match-result reporting.
- Market comparison remains read-only and never becomes betting advice.

## P7: Dashboard / API

- [ ] Create or organize `/api/health`.
- [ ] Create source health matrix.
- [ ] Create fixture board payload.
- [ ] Create prediction evidence payload.
- [ ] Create market consensus payload.
- [ ] Add pytest coverage.

Acceptance criteria:

- Health output includes source status and report freshness.
- Fixture board payload includes provenance-aware source state.
- Prediction evidence explains model inputs without exposing forbidden betting outputs.

## P8: Tournamental Benchmark

- [ ] Create read-only Tournamental adapter.
- [ ] Support `get_match_catalogue`.
- [ ] Support `get_odds`.
- [ ] Support `get_injuries`.
- [ ] Support `get_weather`.
- [ ] Do not submit picks.
- [ ] Keep `TOURNAMENTAL_ENABLE_PICK_SUBMISSION` default false.
- [ ] Add pytest coverage.

Acceptance criteria:

- Adapter has no write methods in phase one.
- Pick submission remains disabled even when env is missing.
- Tournamental data is labeled as benchmark or external signal, not official source data.

## Next Recommended Task

P0 next unfinished task: create the API-key-must-not-be-written-to-repo check.

Suggested next implementation scope:

- Add a focused test or script that scans committed text files for provider secret patterns.
- Allow safe placeholders and documented non-secret IDs.
- Keep API keys loaded from environment variables only.
- Keep the round under 3 to 6 files.
