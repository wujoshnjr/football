# AGENTS.md

## Project Goal

This repository is for the 2026 World Cup Football Prediction platform: an engineering-grade, verifiable, traceable, and testable football prediction and data-fusion system.

The project is not a real-money betting system, not an automated wagering system, and not a bookmaker integration. Predictions, odds-derived signals, market signals, news, weather, rankings, fixtures, and standings are used only for research, explainability, validation, source comparison, and paper tracking.

## Controlled Execution Rules

- Work in small, reviewable rounds.
- Each round may modify at most 3 to 6 files unless the user explicitly approves a larger refactor.
- For backlog work, choose the highest-priority unfinished task with the smallest safe scope.
- Do not automatically merge to `main`.
- After each round, commit the completed work and report changed files, added files, test commands, test results, skipped-test reasons, and the recommended next task.
- Do not continue into the next backlog task without user confirmation.
- Stop and request confirmation before any task that affects real wagering, safety rules, API keys, Render environment variables, production deployment, or provider write behavior.

## Safety Rules

- `live_betting` must remain locked and `false` at all times.
- `automated_wagering` must remain `false` at all times.
- Do not connect to, mock as production-ready, or deploy any real betting API.
- Do not create outputs, API responses, database fields, UI labels, logs, reports, or model artifacts that expose `recommended_bet` except in policy documentation or negative tests that prove it is blocked.
- Do not create outputs, API responses, database fields, UI labels, logs, reports, or model artifacts that expose `stake_size` except in policy documentation or negative tests that prove it is blocked.
- Odds and market data may only be used as `market_consensus`, `external_signal`, or `paper_tracking`.
- Market signals are read-only evidence inputs. They must never become bet execution, bet recommendation, or stake sizing outputs.
- Tournamental Bot Arena is read-only in phase one. It is an external prediction benchmark / bot arena / read-only odds-injuries-weather signal, not an official source, not a primary fixture source, and not a real betting source.
- Do not submit picks to Tournamental. `TOURNAMENTAL_ENABLE_PICK_SUBMISSION` must default to `false`.
- Do not change prediction model behavior unless the task explicitly asks for model work.

## Live Betting Locked Rule

Any feature, config flag, endpoint, background job, UI, adapter, or model output that would enable live betting must remain locked off. If a proposed change introduces live odds, real-time market movement, bet execution, bet recommendation, automated wagering, or stake sizing behavior, stop and redesign it as read-only analytics or paper tracking.

Implementation constraints:

- Default all live betting flags to disabled.
- Treat missing live-betting env flags as disabled.
- Treat missing automated wagering env flags as disabled.
- Do not add runtime paths that can submit orders, place picks, or call bookmaker write APIs.
- Tests for market-related code must assert read-only behavior.
- Safety policy tests must fail if live betting or automated wagering becomes enabled by default.

## API Keys and Environment Variables

- Never commit API keys, tokens, secrets, or provider credentials to GitHub.
- All secrets and provider configuration must be read through `os.getenv` or deployment environment variables such as Render Environment Variables.
- `.env.example` may document variable names only; values must be empty or safe placeholders.
- Logs and JSON reports must never print secret values. Reporting whether a key is present is allowed, but the value must be redacted.
- Do not hardcode provider credentials in tests. Use monkeypatching, fixtures, or safe dummy values.
- Stop and request confirmation before changing Render environment variables or production secret configuration.

## Failure Handling

Missing data must not crash ingestion, prediction generation, scheduled jobs, adapter runs, or API responses.

Adapters and ingestion jobs must handle these cases without uncaught exceptions:

- missing API key
- provider authentication failure
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

Every ingestion adapter must emit a JSON report for every run, including skipped and failed runs. The report must be stable enough for CI, logs, audit, and dashboard health checks.

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
- Do not overwrite prior predictions. Add a new version with `model_version` and provenance.
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

## Adapter Requirements

When adding or changing an adapter:

- Read all provider config from environment variables.
- Fail closed and return a JSON report instead of crashing.
- Preserve source provenance on every emitted record.
- Add or update pytest coverage for success, missing key, provider failure, HTTP 429, HTTP 5xx, schema mismatch, and empty response when relevant.
- Do not introduce real betting writes, recommended bet output, or stake sizing output.
- Keep raw provider payloads out of logs unless explicitly sanitized.
- New adapters and services must include pytest coverage in the same round.

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

For adapter or service work, add focused pytest tests under the backend test suite and run the relevant backend tests before merging or asking for review.

## Review Checklist

Before finishing a round, verify:

- The round modified no more than 3 to 6 files unless explicitly approved.
- Live betting remains locked.
- Automated wagering remains false.
- No real betting API is connected.
- No `recommended_bet` output exists outside rule documentation or negative tests.
- No `stake_size` output exists outside rule documentation or negative tests.
- Odds and market data are read-only and limited to market consensus, external signals, or paper tracking.
- Secrets are read only from environment variables and are never committed.
- Missing keys, API failures, 429, 5xx, schema mismatches, and empty responses produce JSON reports instead of crashes.
- Every fixture, standing, prediction, weather item, news item, and market signal keeps source provenance.
- New adapters and services include pytest coverage.
