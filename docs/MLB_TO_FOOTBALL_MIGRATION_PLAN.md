# MLB to Football Migration Plan

Goal: migrate engineering governance patterns from `wujoshnjr/mlb-prediction-app` into `wujoshnjr/football` without copying MLB-specific baseball assumptions.

| MLB component | MLB files | MLB purpose | Football equivalent | Football-specific changes | Implementation priority | Risk | Test requirements |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Project positioning | `README.md` | States paper-only research, no real-money execution, safety fields, reports, workflow. | `README.md`, `PROJECT_CONTEXT.md`, `MODEL_CARD.md`, `DATA_SOURCES.md`. | State World Cup Intelligence Pipeline, 13 football sources, no live betting, no betting advice. | P0 / Phase 14 | Low | Docs review; secret scan once validator exists. |
| Dashboard/API shell | `main.py` | FastAPI dashboard serving report-backed API and HTML. | Football FastAPI dashboard endpoints. | Serve source health, fixtures, prediction evidence, market consensus, data contract. | P2 / Phase 5 | Medium | Endpoint tests: 200, missing env no crash, no API key leakage. |
| Unified source collection | `model.py` | Optional source imports, safe calls, normalized records, shared errors. | `SourceRegistry`, source adapters, fixture/context ingestion. | Use football fixtures, standings, teams, lineups, injuries, weather, rankings, news, market, benchmark sources. | P1 / Phase 3-4 | Medium | Missing env, empty response, 401/403, 429, 5xx, timeout, schema mismatch. |
| Provider client | `scripts/mlb_stats_client.py` | Fetches MLB schedule and context; returns DataFrame or empty on error. | Football provider adapters. | Standardize JSON SourceReport and provenance; no bare DataFrame-only adapter contract. | P1 / Phase 3-4 | Medium | Mock external responses; no real API calls in default tests. |
| Odds client | `scripts/odds_client.py` | Fetches odds, redacts API key, writes diagnostics, classifies suspicious markets. | Football market-consensus adapter/report. | Read-only market consensus / external signal / paper tracking only. Support 1X2 no-vig. | P2 / Phase 10/12 | High | Verify no `recommended_bet`, no `stake_size`, redacted key diagnostics. |
| Runtime config | `config.py` | Feature gates, pipeline version, snapshot policy, sample thresholds. | Football settings/config constants. | Add football safety flags, World Cup IDs, Tournamental read-only flags, 1X2 feature gates. | P0-P1 | Medium | Defaults false for live betting, automated wagering, pick submission. |
| Feature schema | `scripts/feature_schema.py` | Core/tracking/shadow/availability features and schema hash. | `scripts/football_feature_schema.py`. | Football CORE_MODEL_FEATURES, TRACKING_ONLY_FEATURES, AVAILABILITY_FLAG_FEATURES, SHADOW_CANDIDATE_FEATURES. | P1 / Phase 6 | Medium | Reject unknown promotion; ensure market/weather/news stay tracking-only initially. |
| Prediction generation | `prediction.py` | Builds prediction report, model artifact gate, snapshots, market evidence. | Football 1X2 prediction/evidence pipeline. | Support home/draw/away, knockout advance_result, source provenance, paper-only market comparison. | P3 | High | Multiclass probability validation; no forbidden betting outputs; snapshot created pregame only. |
| Risk guard | `scripts/risk_guard.py` | Rejects unsafe candidate signals based on market/feature conditions. | Football safety policy guard. | Convert from candidate approval to safety rejection and paper-only enforcement. | P0 / Phase 0 and later | High | Live betting false, automated wagering false, real-money false, pick submission false. |
| Pregame snapshot store | `scripts/snapshot_store.py` | First valid pregame snapshot, settlement-only result updates, clean sample protection. | `scripts/football_snapshot_store.py`. | Include fixture_id, match_no, competition, stage, group, 1X2 probabilities, advance_result, safety flags. | P2 / Phase 7 | High | First-seen uniqueness; no post-kickoff clean snapshots; settlement cannot mutate features. |
| Finalized outcomes / settlement | `scripts/sample_state_builder.py`, `data/finalized_games.csv` | Links finalized outcomes to snapshots and builds sample state. | Football finalized fixtures and settlement report. | Separate regulation_result from advance_result. | P2 | High | Outcome truth cannot come from prediction snapshot; settlement append/update behavior tested. |
| Sample state | `scripts/sample_state_builder.py` | Canonical sample counts and readiness thresholds. | Football sample state builder. | Count raw/valid/settled/clean samples plus group vs knockout slices. | P2-P3 | Medium | Missing files no crash; thresholds block readiness. |
| Model artifact gate | `scripts/model_artifact_status.py` | Validates model artifact, feature schema hash, sample count, active eligibility. | Football model artifact status. | Fallback to manual_baseline when artifact missing. | P3 / Phase 11 | Medium | Missing artifact no crash; schema mismatch blocks trained artifact. |
| Data contract | `scripts/data_contract_validator.py` | Validates reports, statuses, JSON safety, safety flags. | `scripts/football_data_contract_validator.py`. | Add source report schema, API key scan, forbidden football betting fields, snapshot checks. | P1 / Phase 8 | High | NaN/Infinity, forbidden keys, true safety flags, API key leaks. |
| Pipeline manifest | `scripts/pipeline_manifest.py` | Tracks artifact existence, size, hash, JSON/CSV summaries. | `scripts/football_pipeline_manifest.py`. | Track football reports, fixtures, finalized fixtures, snapshots, market/weather/injury/lineup context. | P2 / Phase 9 | Low | Missing files no crash; JSON/CSV summaries stable. |
| Calibration | `scripts/calibration_report.py` | Binary calibration report, Brier, ECE/MCE, reliability table. | `scripts/football_calibration_report.py`. | Multiclass home/draw/away calibration and knockout slices. | P3 / Phase 10 | Medium | Insufficient sample status; multiclass metrics; no NaN/Infinity. |
| Model vs market | `scripts/baseline_comparison_report.py`, `scripts/market_close_report.py` | Brier/logloss vs market, closing-line value evidence. | `scripts/football_model_vs_market_report.py`. | No-vig 1X2 probabilities; CLV as evidence only. | P3 / Phase 10 | High | Market comparison does not become betting advice; 1X2 probability sums valid. |
| Promotion gate | `scripts/promotion_gate.py` | Blocks production/promotion based on samples, metrics, CLV, calibration, data contract. | `scripts/football_promotion_gate.py`. | Use football sample thresholds and multiclass evidence. | P3 / Phase 11 | High | Low samples block; production_ready false; missing reports no crash. |
| Report sanitizer | `scripts/sanitize_prediction_report.py` | Removes NaN/Infinity-like values before validation. | Football report sanitizer or data contract utility. | Apply to fixture, prediction, source, and market reports. | P2 | Medium | Cleans non-finite values; does not remove provenance. |
| Dashboard export | `scripts/html_report_builder.py`, site artifacts | Builds public static report/dashboard. | Football dashboard payload and optional static export. | Next.js frontend may consume API payloads instead of static HTML. | Later / Phase 14 | Low | Public payload contains no secrets or forbidden betting fields. |
| GitHub Actions / CI | README documented workflow; file path not discovered | Scheduled governance pipeline. | Football safe CI. | No deployment, no API keys, default external API tests skipped. | Phase 13 | Medium | Compile, pytest, contract, manifest; no live provider calls. |
| Tests | `requirements.txt` includes pytest; direct test paths not discovered in this phase | Automated validation. | Football pytest suite. | Add tests in same phase as adapters/services. | All phases | Medium | Mock external APIs; assert no-crash and safety defaults. |

## Priority Summary

P0 / immediate governance:

- Control docs
- safety policy
- no-live-betting tests
- API-key leak checks

P1 / source foundation:

- source registry
- source report schema
- fixture ingestion report shape
- source provenance

P2 / pipeline foundation:

- fixture ingestion service
- snapshot store
- data contract
- pipeline manifest
- endpoint hardening

P3 / model governance:

- football feature schema
- multiclass evaluation/calibration
- model-vs-market report
- promotion/model artifact gates
- Tournamental read-only adapter

Later:

- dashboard polish
- model card / data-source docs
- final migration report

## Key Migration Risks

- Accidentally copying MLB binary prediction into football instead of 1X2.
- Treating market data as betting advice rather than market consensus.
- Adding provider keys to docs/tests/logs.
- Letting missing provider config crash ingestion.
- Promoting lineup/injury/weather/news/market features into active model before schema promotion evidence.
- Treating Tournamental as official or primary fixture data.
- Allowing settlement to rewrite pregame features.
- Claiming production readiness with insufficient samples.

## Testing Strategy

Every implementation phase should include focused pytest coverage.

Minimum repeated test themes:

- Missing env does not crash.
- External APIs are mocked.
- JSON reports have required fields.
- No NaN/Infinity in generated JSON.
- API keys are redacted or absent.
- Safety flags remain false.
- Forbidden betting output keys are absent.
- Source provenance exists.
- Football 1X2 probabilities are valid where applicable.
- Settlement never mutates pregame features.
