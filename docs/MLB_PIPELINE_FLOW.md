# MLB Pipeline Flow

This flow is derived from the MLB repo README plus the actual files read in Phase 1.

## 1. Data Collection

Primary orchestration appears in `model.py` through `UnifiedSportsModel.gather_all_data()`.

Flow:

1. Determine run date.
2. Initialize a result payload and shared `errors` list.
3. Call source clients through `safe_call()`.
4. Convert source-specific DataFrames/dicts into records.
5. Join odds rows to MLB schedule rows where possible.
6. Write a daily source payload under `report/{date}.json`.
7. Raise only when the schedule source itself failed critically.

Observed source categories:

- MLB schedule/context: `scripts/mlb_stats_client.py`
- Statcast/Savant style data
- Retrosheet / pybaseball / sportsipy
- Weather
- Odds
- Probable pitchers
- Injuries
- Bullpen
- Platoon splits
- Umpires

Football migration:

- Replace baseball sources with football fixture, standing, team, lineup, injury, weather, ranking, news, market, and benchmark sources.
- Standardize every source through SourceReport instead of bare DataFrames.
- Keep shared errors/warnings and no-crash behavior.

## 2. Context Collection

MLB context is collected around pitchers, lineups, weather, bullpen, platoon, umpire, and market odds.

Football equivalent context:

- lineups
- injuries
- suspensions
- weather
- FIFA rankings
- team strength
- news
- market consensus
- Tournamental read-only benchmark signals

Context must remain provenance-aware and availability-flagged.

## 3. Feature Schema

`012%20feature_schema.py` is not the file path; the actual file is `scripts/feature_schema.py`.

It defines:

- core model features
- deferred / tracking-only features
- availability flags
- shadow candidates
- feature groups
- schema hash

Pipeline use:

1. Prediction imports the schema.
2. Model artifact gate compares artifact feature hash against current hash.
3. Feature promotion and diagnostics use the same source of truth.

Football migration:

- Create `scripts/football_feature_schema.py`.
- Keep active model inputs conservative.
- Prevent market, injury, lineup, weather, and news features from entering the active model until promoted.

## 4. Prediction Generation

`prediction.py` generates daily predictions.

Key stages:

1. Import optional helpers defensively.
2. Read model artifact gate status.
3. Gather source data through `UnifiedSportsModel`.
4. Build features under the shared schema.
5. Compare model probabilities to market no-vig probabilities.
6. Apply risk/safety guards.
7. Write `report/prediction.json` using JSON-safe values.
8. Append pregame snapshots when configured.
9. Append market snapshots / refresh opening-closing flags when helpers exist.

Football migration:

- Generate 1X2 model probabilities: home/draw/away.
- Handle knockout advance_result separately.
- Preserve source snapshot and provenance.
- Do not emit betting advice or stake sizing.

## 5. Pregame Snapshot

`024%20snapshot_store.py` is not the file path; the actual file is `scripts/snapshot_store.py`.

Rules observed:

- Forward-collected only.
- Eligible only before scheduled start.
- Keep only first valid pregame snapshot per pipeline version and game.
- Settlement writes outcomes only.
- Legacy/backfilled rows are not clean training samples.

Football migration:

- `first_seen_pregame` per fixture and pipeline version.
- Include kickoff, group/stage, home/away, 1X2 model probabilities, market probabilities, source snapshot, safety flags, and settlement fields.
- Settlement cannot mutate pregame features.

## 6. Settlement

MLB settlement links snapshots to finalized games. `scripts/sample_state_builder.py` reads:

- `data/prediction_snapshots.csv`
- `data/finalized_games.csv`
- `data/finalized_snapshot_outcomes.csv`
- training status and model artifact status

It derives clean sample counts and readiness.

Football migration:

- Use finalized fixtures as outcome truth.
- Keep regulation result separate from knockout advance_result.
- Never use prediction snapshots as outcome sources.

## 7. Calibration

`021%20calibration_report.py` is not the file path; the actual file is `scripts/calibration_report.py`.

Observed behavior:

- Reads OOS predictions.
- Handles missing or empty inputs with skipped/error reports.
- Computes Brier, expected calibration error, maximum calibration error, and reliability table.
- Writes JSON without NaN/Infinity.

Football migration:

- Use multiclass Brier and multiclass LogLoss.
- Produce home/draw/away calibration.
- Report insufficient samples instead of overstating readiness.

## 8. CLV / Model vs Market

Observed scripts:

- `scripts/baseline_comparison_report.py`
- `scripts/market_close_report.py`

Flow:

1. Link snapshots and finalized results.
2. Compute model metrics.
3. Compute market no-vig baseline metrics.
4. Compare model vs constant, historical, Elo, and market baselines.
5. Link entry snapshots to closing odds where possible.
6. Produce CLV and market-movement evidence.

Football migration:

- Use no-vig 1X2 market probabilities.
- Compare `model_home_prob`, `model_draw_prob`, `model_away_prob` against market equivalents.
- Keep CLV as evidence only, never as betting advice.

## 9. Risk Guard

`unsafe betting approval` is not the football migration target.

MLB has `scripts/risk_guard.py`, which rejects weak or unsafe market candidates based on feature health, lineup status, and historical CLV buckets.

Football migration:

- Convert the pattern into a paper-only safety gate.
- Block live betting, automated wagering, real-money betting, pick submission, betting advice, `recommended_bet`, and `stake_size`.
- Keep market evidence read-only.

## 10. Promotion Gate

`srcipts/promotion_gate.py` is not the file path; the actual file is `scripts/promotion_gate.py`.

Observed gate inputs:

- training status
- sample state
- sample state report
- baseline comparison
- calibration
- walk-forward evaluation
- rolling walk-forward evaluation
- CLV / market-close reports
- research quality
- data contract
- pipeline manifest

Observed blockers:

- insufficient clean samples
- insufficient walk-forward predictions
- model not beating market Brier/logloss
- missing or non-positive CLV
- calibration not ready
- data contract not ok
- research quality low
- live betting disabled by governance

Football migration:

- Use football sample thresholds.
- Use multiclass metrics.
- Keep production readiness blocked until enough clean evidence exists.

## 11. Report Generation

Common report style:

- `generated_at`
- `status`
- `input_files`
- counts
- warnings/errors
- safety flags
- JSON-safe values

Important report scripts read:

- prediction report generation in `prediction.py`
- sanitization in `scripts/sanitize_prediction_report.py`
- calibration in `scripts/calibration_report.py`
- baseline comparison in `scripts/baseline_comparison_report.py`
- market close in `scripts/market_close_report.py`
- promotion gate in `scripts/promotion_gate.py`
- data contract in `scripts/data_contract_validator.py`
- pipeline manifest in `scripts/pipeline_manifest.py`

Football migration:

- Every adapter and pipeline step should write stable JSON reports.
- Reports must be valid JSON with no NaN/Infinity.
- Reports must not leak API keys.

## 12. Dashboard Export

`main.py` serves dashboard/API directly. `scripts/html_report_builder.py` can build static dashboard HTML from public dashboard data or generated dashboard payloads.

Football migration:

- Keep FastAPI endpoints for app use.
- Build safe dashboard payloads from artifacts.
- Avoid making external API calls on normal dashboard requests.

## 13. Data Contract Validation

`012%20data_contract_validator.py` is not the file path; the actual file is `scripts/data_contract_validator.py`.

Validation flow:

1. Check required JSON reports.
2. Check optional reports when present.
3. Validate status fields.
4. Validate JSON cleanliness.
5. Validate safety flags.
6. Validate prediction fields.
7. Emit data contract report.

Football migration:

- Add source report schema validation.
- Block forbidden keys: `recommended_bet`, `stake_size`.
- Block true live-betting / automated-wagering / real-money flags.
- Scan tracked text files for API-key leaks.

## 14. Pipeline Manifest

`021%20pipeline_manifest.py` is not the file path; the actual file is `scripts/pipeline_manifest.py`.

Manifest flow:

1. Iterate a declared list of artifacts.
2. For each file, record existence and size.
3. Hash files with SHA-256.
4. Summarize JSON and CSV artifacts.
5. Emit `report/pipeline_manifest.json`.

Football migration:

- Start with a smaller football artifact list.
- Include source health, fixture ingestion, predictions, snapshots, finalized fixtures, market history, weather, injuries, lineups, sample state, data contract, and manifest itself.

## 15. GitHub Actions Execution Order

No workflow file was found through connector path attempts in Phase 1. README documents intended scheduled workflow order:

1. Checkout repo.
2. Install dependencies.
3. Compile critical Python files.
4. Update finalized results.
5. Build sample state.
6. Train only if enough finalized samples exist.
7. Collect context data.
8. Generate prediction report.
9. Sanitize prediction outputs.
10. Build evaluation reports.
11. Build promotion / governance reports.
12. Build world-class and SaaS readiness reports.
13. Build dashboard HTML.
14. Run data contract validation.
15. Run tests.
16. Validate health gates.
17. Upload artifacts.
18. Commit selected generated outputs.

Football migration:

- CI should install dependencies, compile critical files, run pytest, run data contract validator if available, run pipeline manifest if available, and avoid deployment/API keys/external API calls by default.
