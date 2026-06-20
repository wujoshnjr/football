# Football Architecture Gap Analysis

This document compares the current `wujoshnjr/football` architecture against the MLB reference architecture and the project safety rules. It is based on files read from the football branch `codex/engineering-control-docs` and the MLB research docs created in Phase 1.

## Scope

Phase 2 is documentation only. It does not change prediction model behavior, adapters, API endpoints, Render environment variables, deployment settings, or any betting-related behavior.

Reviewed football files:

- `README.md`
- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/schemas.py`
- `backend/app/safety_policy.py`
- `backend/app/services/source_fusion_service.py`
- `backend/app/services/fixture_ingestion_service.py`
- `backend/app/services/prediction_service.py`
- `backend/app/services/advanced_feature_registry.py`
- `backend/app/services/feature_table_service.py`
- `backend/app/services/sources/base.py`
- `backend/app/services/sources/registry.py`
- `backend/app/services/sources/sportsdataio.py`
- `backend/app/services/sources/tournamental_bot_arena.py`
- `backend/tests/test_safety_policy.py`
- `backend/requirements.txt`

## Current File Purpose Table

| Path | Current purpose | MLB-like equivalent | Keep / refactor / add |
| --- | --- | --- | --- |
| `README.md` | MVP overview, backend/frontend startup, first model description, source planning. | Project overview and workflow guidance. | Keep, later update in Phase 14 to reflect safety policy, canonical sources, and evaluation limits. |
| `backend/app/main.py` | FastAPI app with health, data-source, ingestion, fixture, feature, market, Tournamental, and prediction routes. | MLB app/API surface and dashboard payload producer. | Keep, later tighten endpoint contracts and safety sanitization. |
| `backend/app/config.py` | Pydantic settings for provider keys, base URLs, feature toggles, SportsDataIO IDs, TheStatsAPI IDs, and Tournamental flags. | MLB config layer. | Keep, later verify defaults and env naming through SourceRegistry tests. |
| `backend/app/schemas.py` | Pydantic schemas for fixtures, teams, probabilities, source context, prediction diagnostics, and responses. | MLB typed prediction/data contract layer. | Keep, later extend with provenance objects and source report schemas. |
| `backend/app/safety_policy.py` | Locked safety policy for live betting, automated wagering, pick submission, forbidden output keys, and market roles. | MLB risk guard / safety guard. | Keep, then wire into data contract and API response validation. |
| `backend/tests/test_safety_policy.py` | Tests that live betting and pick submission stay locked false and forbidden output keys are rejected. | MLB risk guard tests. | Keep, expand in P0/P1 to scan endpoints and artifacts. |
| `backend/app/services/source_fusion_service.py` | In-app source registry and source reliability context for model adjustment. | MLB source context and data-source health summary. | Refactor toward canonical `SourceRegistry` with exactly 13 project sources. |
| `backend/app/services/sources/registry.py` | Lists adapter classes for fixture sources and feature/benchmark sources. | MLB provider registry. | Refactor to share metadata with SourceRegistry instead of duplicating source truth. |
| `backend/app/services/sources/base.py` | Base adapter, `SourceAdapterResult`, HTTP JSON fetch, URL redaction, and no-crash provider failure handling. | MLB data client safe-call and report foundation. | Keep, extend to canonical SourceReport schema. |
| `backend/app/services/fixture_ingestion_service.py` | Runs adapters, normalizes records, dedupes fixtures, returns an ingestion report-like payload. | MLB data collection and normalization stage. | Keep, add persisted JSON report and richer provenance. |
| `backend/app/services/prediction_service.py` | Current Elo/Poisson/market-consensus 1X2 baseline with diagnostics and explanations. | MLB prediction layer. | Keep untouched until later model/evaluation phases. |
| `backend/app/services/feature_table_service.py` | Builds pre-match feature rows from fixtures, source context, and optional market consensus. | MLB feature schema / feature table builder. | Keep, later put features behind explicit football feature schema. |
| `backend/app/services/advanced_feature_registry.py` | Documents candidate advanced features and leakage risk. | MLB feature schema planning. | Keep as planning input; not a promotion gate yet. |
| `backend/app/services/sources/sportsdataio.py` | SportsDataIO read-only fixture adapter using configured World Cup IDs. | MLB external provider adapter. | Keep, add SourceReport metadata and mocked pytest coverage. |
| `backend/app/services/sources/tournamental_bot_arena.py` | Tournamental Bot Arena readiness adapter; does not produce fixtures or submit picks. | MLB market/external benchmark adapter. | Refactor later to hard-fail any pick-submission enable request and add read-only methods. |
| `backend/requirements.txt` | Backend runtime and test dependencies. | MLB dependency baseline. | Keep, add dependencies only when tests or implementation require them. |

## Existing MLB-Like Architecture

The football repo already has useful architecture that should not be discarded:

- FastAPI route organization exists in `backend/app/main.py`.
- Pydantic settings centralize provider configuration in `backend/app/config.py`.
- Pydantic response schemas exist for fixtures, predictions, source context, and diagnostics.
- `SourceFusionService` already exposes data-source registry and context endpoints.
- `BaseSourceAdapter` already catches missing URL, missing credentials, HTTP errors, JSON parse errors, schema mismatches, empty responses, timeouts, and upstream HTTP errors without crashing.
- `SourceAdapterResult` already returns a JSON-serializable report shape with status, error, record counts, redacted URL, latency, and retryability.
- `FixtureIngestionService` already coordinates adapters and normalizes/dedupes fixtures.
- The prediction layer already models football as home/draw/away, not MLB binary outcome.
- Market data is already framed as `market_consensus` inside prediction components.
- `safety_policy.py` and `test_safety_policy.py` provide a strong starting point for locked no-live-betting behavior.

## Missing MLB-Like Architecture

The project is not yet at MLB-level engineering maturity in these areas:

- No canonical standalone `scripts/source_registry.py` that contains exactly the 13 approved project sources and their metadata.
- No standalone `scripts/source_report_schema.py` that every adapter and health report validates against.
- No persisted `fixture_ingestion_report.json` artifact with run ID, source reports, merged counts, warnings, errors, and provenance summary.
- No football snapshot store equivalent to MLB pregame snapshot and settlement discipline.
- No football feature schema that separates active model features from tracking-only, availability flags, and shadow candidates.
- No football data contract validator for JSON finite values, required reports, safety flags, API key leakage, and forbidden betting output fields.
- No pipeline manifest that hashes and summarizes expected report/data artifacts.
- No multiclass football evaluation reports for Brier, LogLoss, calibration, model-vs-market, group-stage slices, and knockout advance-result slices.
- No promotion gate or model artifact gate that blocks production claims when sample counts are too low.
- No CI workflow verification found yet. This remains for Phase 13.

## Duplicated Or Confusing Areas

| Area | Observation | Risk | Recommendation |
| --- | --- | --- | --- |
| Source lists | `SourceFusionService.registry()` includes the 13 canonical sources plus extra sources such as ESPN, HumHub, Tournamental odds, OpenFootball text, soccerdata package, and GitHub scraper projects. `sources/registry.py` has a separate adapter class list. | Source truth can drift across endpoints, adapters, docs, and tests. | Phase 3 should create canonical SourceRegistry and let extra sources be explicitly tagged as non-canonical or future candidates. |
| Tournamental naming | Code uses `tournamental_bot_arena` as the current key. The product name is Tournamental Bot Arena. | Typos in docs/env can create duplicate source identities. | Keep one canonical code key and document aliases only if needed. |
| Tournamental pick submission | `tournamental_bot_arena.py` returns an OK readiness status even when pick submission is enabled, saying ingestion does not use it. | Safety policy requires pick submission to remain false, not merely unused by ingestion. | Later phase should make adapter/report status unsafe or disabled when pick submission is requested. |
| Source metadata | `DataSourceStatus` and `SourceAdapterResult` contain overlapping but different metadata. | Endpoints may show configured/enabled while adapters report a different status. | Phase 3 should define one SourceReport schema and map existing structures into it. |
| Fixture provenance | Normalized fixtures retain `source_key` and `source_event_id`, but dedupe keeps one winning source and drops cross-source evidence. | Fixture lineage cannot explain all contributing sources after merge. | Phase 4 should add `source_provenance` arrays and preserve rejected/merged source candidates. |
| README source priority | README still says first source is API-Football with Football-Data backup. | It is narrower than the current 13-source plan. | Phase 14 should update README after implementation catches up. |
| TheSportsDB default key | `thesportsdb_api_key` defaults to `123`, which may be a public test key but still looks key-like. | Static key-like defaults can confuse no-key policy and secret scans. | Keep for now if it is provider-public, but document and test that private keys are env-only. |

## Files To Keep

- `backend/app/main.py`, with later endpoint contract hardening.
- `backend/app/config.py`, with later registry-driven env validation.
- `backend/app/schemas.py`, with provenance and report schema additions.
- `backend/app/safety_policy.py` and `backend/tests/test_safety_policy.py`.
- `backend/app/services/sources/base.py`, because it already contains the no-crash HTTP adapter foundation.
- `backend/app/services/fixture_ingestion_service.py`, because it already coordinates adapter ingestion and normalization.
- `backend/app/services/prediction_service.py`, kept untouched for now.
- `backend/app/services/feature_table_service.py`, kept as the seed for football feature schema work.

## Files To Refactor Later

- `backend/app/services/source_fusion_service.py`: move canonical source metadata into SourceRegistry and avoid extra-source confusion.
- `backend/app/services/sources/registry.py`: build adapter lists from registry metadata where practical.
- `backend/app/services/sources/tournamental_bot_arena.py`: enforce read-only locked behavior even when env attempts to enable pick submission.
- `backend/app/services/fixture_ingestion_service.py`: persist reports, preserve full provenance, and standardize run metadata.
- `backend/app/services/feature_table_service.py`: require football feature schema before promotion into active model inputs.
- `README.md`: update after source registry, ingestion, and safety policy are implemented.

## Files To Add

Near-term files from the backlog:

- `scripts/source_registry.py`
- `scripts/source_report_schema.py`
- `tests/test_source_registry.py`
- `scripts/fixture_ingestion_service.py` or backend-aligned ingestion entrypoint if the existing service remains the canonical implementation
- `tests/test_fixture_ingestion_service.py`
- `scripts/football_feature_schema.py`
- `scripts/football_snapshot_store.py`
- `scripts/football_data_contract_validator.py`
- `scripts/football_pipeline_manifest.py`
- football evaluation, promotion gate, and model artifact status scripts

## Test Gaps

Existing safety policy tests are useful, but coverage is still missing for:

- Canonical source registry metadata and missing env behavior.
- SourceReport schema validation for every adapter status.
- Adapter no-crash behavior for 401, 403, 429, 5xx, timeout, parse error, schema mismatch, and empty response.
- Fixture ingestion report generation and persistence.
- Fixture dedupe with provenance preservation.
- API endpoints returning safe payloads without secrets or forbidden betting fields.
- Tournamental read-only behavior and pick-submission lock.
- Feature schema promotion rules.
- Snapshot first-seen-pregame immutability and settlement rules.
- Data contract checks for NaN, Infinity, required reports, safety flags, and API-key leaks.
- Multiclass football evaluation metrics.
- CI execution of pytest and contract checks.

## Adapter JSON Report Gaps

`SourceAdapterResult` is a good base, but it does not yet fully satisfy the project-wide standard report contract:

- It uses `ok` while the planned schema asks for `success`.
- It uses `generated_at` while the planned schema asks for `checked_at`.
- It does not include `source` as a nested metadata object.
- It does not include `missing_env`.
- It does not include canonical source `official`, `role`, `production_use`, or priority metadata.
- It does not distinguish canonical sources from future/extra sources.
- It does not validate report JSON centrally.
- It can include records internally, but report mode usually strips records, so provenance must be captured elsewhere.

Phase 3 should not delete `SourceAdapterResult`; it should define a canonical SourceReport schema and provide a mapper from adapter results into that schema.

## API No-Crash Risk Review

Strengths already present:

- `BaseSourceAdapter.fetch_json()` returns report objects for missing URL, disabled source, non-200 HTTP status, JSON decode failure, schema mismatch, empty response, timeout, and generic HTTP errors.
- `FixtureIngestionService._safe_fetch()` catches adapter exceptions during bulk ingestion and returns an adapter report.
- URL redaction exists for sensitive query parameters and bearer-like tokens.

Remaining risks:

- `_fetch_single()` does not wrap exceptions with `_safe_fetch()`, so legacy wrapper calls could still crash if an adapter raises unexpectedly.
- `FixtureIngestionService.ingest()` uses `asyncio.run()`, which is fine from sync FastAPI handlers but can fail if reused inside an existing event loop.
- Normalizers are defensive, but they are not covered by broad schema-mismatch tests for all providers.
- Endpoint-level exception handling still needs tests for missing artifact files, malformed cached JSON, and provider health failures.
- Tournamental pick-submission env requests are not treated as adapter errors yet.

## Source Provenance Gaps

Current state:

- Normalized fixture records include `source_key` and `source_event_id`.
- Source context includes aggregate lists of configured, used, and missing sources.
- Feature table rows include market source event ID and sport key when matched.

Required future state:

- Every fixture should carry a `source_provenance` array with source key, source event ID, fetched/checked timestamp, raw provider path or redacted URL, adapter status, and merge role.
- Dedupe should preserve all candidate source records, not only the winning source.
- Every prediction should include provenance for fixture, feature context, market signal, weather, news, rankings, and model version.
- Weather and news records should include source, query, checked timestamp, and relation to fixture or team.
- Market signals must be labeled only as `market_consensus`, `external_signal`, or `paper_tracking`.
- Tournamental Bot Arena records must be read-only external benchmark provenance, never official fixture truth.

## No-Live-Betting Policy Gaps

Existing safeguards:

- `safety_policy.py` locks live betting, automated wagering, real-money betting, and pick submission false at the policy layer.
- `test_safety_policy.py` verifies env attempts cannot unlock those policy outputs.
- Forbidden output key detection exists for `recommended_bet` and `stake_size`.

Remaining gaps:

- The safety policy is not yet enforced as a data contract over generated reports and API payloads.
- Endpoint responses are not centrally scanned for forbidden betting fields.
- Tournamental adapter readiness does not fail when pick-submission env is true.
- Data contract validator does not yet exist to block unsafe artifacts.
- CI does not yet run a no-live-betting policy test or API-key leak scan.

## P0/P1/P2/P3 Implementation Order

P0: Engineering safety hardening

- Keep `AGENTS.md`, `PROJECT_CONTEXT.md`, and `CODEX_BACKLOG.md` as the controlling policy documents.
- Add safety-policy tests that scan representative endpoint/report payloads.
- Add an API-key leak scanner for tracked text files.
- Define the central source report schema before expanding ingestion.

P1: SourceRegistry and SourceReport schema

- Create canonical SourceRegistry with exactly the 13 approved sources.
- Include `key`, `name`, `requires_key`, `official`, `role`, `production_use`, `priority`, `env_vars`, `enabled_env`, `configured`, and `missing_reason`.
- Map existing `SourceFusionService` and adapter results to the canonical registry.
- Keep extra sources outside the canonical list unless explicitly promoted later.

P2: Fixture ingestion

- Use only phase-one fixture sources: `football_data`, `api_football`, `worldcup_2026_api`, `openfootball_worldcup_json`, `sportsdataio_worldcup`, and `thestatsapi_worldcup`.
- Persist `fixture_ingestion_report.json` or provide deterministic generation logic.
- Preserve source provenance for every fixture.
- Mock all external APIs in tests.

P3: Snapshot and contract foundation

- Add first-seen-pregame snapshot storage.
- Add settlement-only post-match results.
- Add data contract checks for required reports, finite JSON, safety flags, forbidden fields, and API-key leakage.
- Add pipeline manifest once report artifacts exist.

## Immediate Next Phase

Phase 3 should implement the canonical SourceRegistry and SourceReport schema first. That gives later ingestion, endpoints, reports, and tests one stable contract instead of hard-coding source metadata in multiple places.
