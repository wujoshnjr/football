# Evaluation Method

## Scope

Evaluation is retrospective, paper-only, and research-only. It must not produce wagering instructions, stake sizing, or real-money betting actions.

The core prediction target is 1X2:

- `home_win`
- `draw`
- `away_win`

Knockout matches may additionally track `advance_result`, but advancement must be evaluated separately from the regulation-time 1X2 result.

## Required Reports

Evaluation-related reports include:

- `report/calibration_report.json`
- `report/model_vs_market_report.json`
- `report/promotion_gate_report.json`
- `report/model_artifact_status_report.json`
- `report/data_contract_report.json`
- `report/pipeline_manifest.json`

Reports must be JSON-safe and contain no `NaN` or `Infinity` values.

## Metrics

### Multiclass Brier Score

For each fixture, Brier score is the sum of squared differences between predicted probabilities and the one-hot actual outcome vector:

```text
sum((p_i - y_i)^2 for i in [home_win, draw, away_win])
```

The report average is the mean over settled samples.

### Multiclass LogLoss

LogLoss uses the predicted probability assigned to the actual outcome:

```text
-log(max(epsilon, p_actual))
```

Probabilities are clipped only for numeric stability.

### Calibration

Calibration must be reported for all three 1X2 outcomes:

- home win
- draw
- away win

Each outcome should include probability bins with sample count, average predicted probability, and observed frequency.

## Slices

Reports should include at least:

- group-stage samples
- knockout samples
- favorite-result samples
- underdog-or-draw-result samples

The purpose is diagnostic. Slices with low sample counts must not be used as production proof.

## Sample Count Guard

Low sample counts must report `insufficient_sample`.

Minimum governance thresholds:

- `clean_train_samples >= 300` before production model claims
- `settled_predictions >= 500` before formal calibration conclusions
- `production_samples >= 1000` before `production_ready`

The promotion gate must block readiness claims when thresholds are not met.

## Model Vs Market

Market comparison is read-only evidence. It may use no-vig 1X2 implied probabilities:

- `market_home_prob`
- `market_draw_prob`
- `market_away_prob`

Allowed roles:

- `market_consensus`
- `external_signal`
- `paper_tracking`

Model-vs-market reports may include:

- average absolute model-market probability gap
- per-outcome signed gap
- market favorite agreement rate
- group-stage vs knockout gaps
- favorite vs underdog gaps
- market movement evidence
- CLV-style diagnostics for paper tracking only

Market comparison must not become betting advice.

## Snapshot Rules

Evaluation samples should come from clean pregame snapshots:

- generated before kickoff
- first seen for the fixture and pipeline version
- immutable after kickoff
- settled only with post-match result columns
- carrying source provenance and feature schema hash

Backfilled rows must not be counted as clean forward-collected samples unless explicitly marked and validated.

## Data Quality

Evaluation must account for:

- missing source provenance
- missing actual outcomes
- invalid or non-normalized probabilities
- provider schema mismatch
- unavailable market consensus
- unavailable weather, lineup, injury, or news context
- group-stage vs knockout differences
- draw calibration risk

Invalid rows should be skipped with explicit skipped-reason counts instead of crashing.

## Promotion Interpretation

Promotion gates are audit reports, not deployment tools. A passing gate may support a readiness claim only if safety locks remain false and sample thresholds are met.

A failing gate must keep the project in manual baseline or shadow mode.

Allowed model sources:

- `manual_baseline`
- `trained_artifact`
- `shadow_model`

Missing artifacts must fall back to `manual_baseline` without crashing.

## Test Expectations

Evaluation tests should use static rows, mocks, fake clients, or temporary files. They must not call external APIs and must not require provider API keys.

Focused test commands:

```bash
pytest tests/test_football_evaluation.py
pytest tests/test_football_promotion_gate.py
```
