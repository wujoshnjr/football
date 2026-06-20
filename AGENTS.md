# AGENTS.md

## Project Goal

This repository is the 2026 World Cup Football Prediction project. The target state is a World Cup Intelligence Pipeline: an engineering-grade, verifiable, traceable, testable football prediction and data-fusion platform.

The project is not a real-money betting product, not an automated wagering system, and not a bookmaker integration. Predictions, odds-derived signals, market signals, news, weather, rankings, fixtures, standings, lineups, injuries, and model outputs are used only for research, explainability, validation, source comparison, and paper tracking.

## Codex Execution Mode

Codex should act as the repo engineering agent and advance work in phases. The default posture is proactive: read relevant files, plan the smallest safe change, implement, add or update tests, run the most relevant tests, commit, update `CODEX_EXECUTION_LOG.md`, update `CODEX_BACKLOG.md`, and continue to the next phase.

Stop and ask for confirmation only when one of these conditions is true:

- Required repository access is missing.
- A task requires a plaintext API key or secret value.
- A task changes Render environment variables.
- A task deploys or modifies production deployment behavior.
- A task enables real betting, live betting, automated wagering, pick submission, or a sportsbook write path.
- A task requires merging to `main` or deleting many files.
- Tests fail after three automatic repair attempts.
- A task may weaken or violate these safety rules.

Do not merge to `main` automatically. Work on a feature branch and commit completed phase work there.

## Safety Rules

- `live_betting` must remain locked and `false` at all times.
- `automated_wagering` must remain `false` at all times.
- `real_money_betting_allowed` must remain `false` at all times.
- `production_allowed` must remain `false` unless the user explicitly starts a production deployment task.
- Do not connect to, mock as production-ready, or deploy any real betting API.
- Do not output betting advice.
- Do not create outputs, API responses, database fields, UI labels, logs, reports, or model artifacts that expose `recommended_bet` except in policy documentation or negative tests that prove it is blocked.
- Do not create outputs, API responses, database fields, UI labels, logs, reports, or model artifacts that expose `stake_size` except in policy documentation or negative tests that prove it is blocked.
- `stake_multiplier` must be `0` or absent.
- Odds and market data may only be used as `market_consensus`, `external_signal`, or `paper_tracking`.
- Market signals are read-only evidence inputs. They must never become bet execution, bet recommendation, betting advice, or stake sizing outputs.
- Tournamental Bot Arena is read-only in phase one. It is an external prediction benchmark / bot arena / read-only odds, injuries, and weather signal. It is not official, not a primary fixture source, not a primary score source, and not a real-money betting source.
- Do not submit picks to Tournamental. `TOURNAMENTAL_ENABLE_PICK_SUBMISSION` must default to `false`.
- Do not change prediction model behavior unless the current phase explicitly requires model work.

## Live Betting Locked Rule

Any feature, config flag, endpoint, background job, UI, adapter, script, report, or model output that would enable live betting must remain locked off. If a proposed change introduces live odds, real-time market movement, bet execution, bet recommendation, automated wagering, pick submission, or stake sizing behavior, stop and redesign it as read-only analytics or paper tracking.

Implementation constraints:

- Default all live betting flags to disabled.
- Treat missing live-betting env flags as disabled.
- Treat missing automated wagering env flags as disabled.
- Treat missing Tournamental pick-submission env flags as disabled.
- Do not add runtime paths that can submit orders, place picks, or call bookmaker write APIs.
- Tests for market-related code must assert read-only behavior.
- Safety policy tests must fail if live betting, automated wagering, real-money betting, or pick submission becomes enabled by default.

## API Keys and Environment Variables

- Never commit API keys, tokens, secrets, or provider credentials to GitHub.
- Never put API keys in test fixtures, README files, docs, generated reports, logs, or examples.
- All secrets and provider configuration must be read through `os.getenv`, Pydantic settings backed by env vars, or deployment environment variables such as Render Environment Variables.
- `.env.example` may document variable names only; values must be empty or safe placeholders.
- Logs and JSON reports must never print secret values. Reporting whether a key is present is allowed, but the value must be redacted.
- Tests must use mocks, monkeypatching, fixtures, or safe dummy values. Tests must not require real provider keys.
- Stop and request confirmation before changing Render environment variables or production secret configuration.

## Failure Handling

Missing data must not crash ingestion, prediction generation, scheduled jobs, adapter runs, scripts, reports, tests, or API responses.

Adapters and ingestion jobs must handle these cases without uncaught exceptions:

- missing API key
- provider authentication failure
- HTTP 401 / 403
- network timeout
- HTTP 429
- HTTP 5xx
- malformed response body
- schema mismatch
- empty response
- empty dataset
- partial provider outage

When a provider cannot be used, return a structured JSON report with `status` set to `skipped`, `partial`, or `failed`, plus a clear non-secret reason.

## Adapter JSON Report Standard

Every ingestion adapter must emit a JSON report for every run, including skipped and failed runs. The report must be stable enough for CI, logs, audit, source health, data contracts, and dashboard health checks.

Required report shape:

```json
{
  "adapter": "api_football",
  "source": "api_football",
  "run_id": "2026-01-01T00:00:00Z-api_football",
  "status": "ok|partial|skipped|failed",
  "started_at": "2026-01-01T00:00:00Z",
  "finished_at": "2026-01-01T00:00:03Z",
  "records": {
    "fetched": 0,
    "accepted": 0,
    "rejected": 0,
    "written": 0
  },
  "http": {
    "status_code": null,
    "retry_after_seconds": null
  },
  "errors": [],
  "warnings": [],
  "schema_version": "adapter-report-v1",
  "secrets": {
    "required": ["API_FOOTBALL_KEY"],
    "present": false,
    "redacted": true
  },
  "output": {
    "path": null,
    "checksum": null
  },
  "provenance": []
}
```

Rules:

- Use `ok` only when the adapter completed the intended fetch and validation path.
- Use `partial` when some records were usable but provider or schema issues affected completeness.
- Use `skipped` when required configuration is missing or the source is intentionally disabled.
- Use `failed` only for handled failures that prevented useful records from being produced.
- `errors` and `warnings` must be arrays of structured objects or concise strings safe for logs.
- Never include raw secrets or full sensitive request headers.
- JSON reports must not contain NaN, Infinity, or non-serializable values.

## Source Provenance Rules

Every fixture, standing, prediction, weather item, news item, and market signal must retain source provenance.

Minimum provenance fields:

```json
{
  "source": "football_data",
  "source_type": "fixture|standing|prediction|weather|news|ranking|market|benchmark",
  "provider_record_id": "optional-provider-id",
  "source_url": "https://example.com/source-or-endpoint",
  "fetched_at": "2026-01-01T00:00:00Z",
  "adapter": "football_data",
  "adapter_version": "v1",
  "license": "unknown-or-provider-license",
  "raw_payload_checksum": "sha256:..."
}
```

Rules:

- Derived predictions must preserve provenance for all upstream fixture, standing, ranking, weather, news, injury, market, and benchmark inputs used.
- Do not overwrite prior predictions. Add a new version with `model_version`, `feature_version`, `pipeline_version`, and provenance.
- If a provider record has no stable ID, create a deterministic checksum-based ID and record the fields used.
- For conflicting sources, keep all source records and resolve downstream with explicit precedence logic.
- Market-signal provenance must label the role as `market_consensus`, `external_signal`, or `paper_tracking`.

## Approved Data Source Names

Use these canonical source names in adapters, reports, provenance, config, tests, and documentation:

- `football_data`
- `api_football`
- `worldcup_2026_api`
- `openfootball_worldcup_json`
- `zafronix_worldcup`
- `thesportsdb_worldcup`
- `statsbomb_open_data`
- `open_meteo_weather`
- `gdelt_news`
- `fifa_ranking_source`
- `sportsdataio_worldcup`
- `thestatsapi_worldcup`
- `tournamental_bot_arena`

If the typo `tournamental_bot_arena` appears in user notes, normalize it to the canonical repo key `tournamental_bot_arena`.

## Football-Specific Modeling Rules

Do not copy MLB binary prediction assumptions directly into football.

Football predictions must support:

- Group-stage / standard 1X2: `home_win`, `draw`, `away_win`.
- Knockout reporting: `regulation_result` and `advance_result`.
- Market no-vig 1X2 fields: `market_home_prob`, `market_draw_prob`, `market_away_prob`.
- Model 1X2 fields: `model_home_prob`, `model_draw_prob`, `model_away_prob`.
- Pregame snapshots with `first_seen_pregame`, `kickoff_time`, `generated_at`, `source_snapshot`, `feature_version`, `model_version`, and `pipeline_version`.
- Settlement that never mutates pregame features.

## Adapter and Service Requirements

When adding or changing an adapter or service:

- Read all provider config from environment variables.
- Fail closed and return a JSON report instead of crashing.
- Preserve source provenance on every emitted record.
- Add or update pytest coverage for success, missing key, provider failure, HTTP 401 / 403, HTTP 429, HTTP 5xx, timeout, schema mismatch, and empty response when relevant.
- Do not introduce real betting writes, recommended bet output, betting advice, pick submission, or stake sizing output.
- Keep raw provider payloads out of logs unless explicitly sanitized.
- New adapters and services must include pytest coverage in the same phase.

## Test Commands

Backend tests:

```bash
cd backend
pytest
```

Backend dependency setup when needed:

```bash
cd backend
pip install -r requirements.txt
```

Frontend build check:

```bash
cd frontend
npm install
npm run build
```

For adapter or service work, add focused pytest tests under the backend or project test suite and run the relevant tests before committing when the local environment supports it.

## Phase Completion Checklist

Before finishing each phase, verify:

- The phase stayed within the planned scope.
- Live betting remains locked.
- Automated wagering remains false.
- Real-money betting remains false.
- No real betting API is connected.
- No `recommended_bet` output exists outside policy documentation or negative tests.
- No `stake_size` output exists outside policy documentation or negative tests.
- Odds and market data are read-only and limited to market consensus, external signals, or paper tracking.
- Secrets are read only from environment variables and are never committed.
- Missing keys, API failures, 401 / 403, 429, 5xx, timeouts, schema mismatches, and empty responses produce reports instead of crashes.
- Every fixture, standing, prediction, weather item, news item, and market signal keeps source provenance.
- New adapters and services include pytest coverage.
- `CODEX_BACKLOG.md` and `CODEX_EXECUTION_LOG.md` are updated.
- Completed work is committed to the working branch, not merged to `main`.
