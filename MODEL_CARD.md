# MODEL_CARD.md

## Model Purpose

This project estimates 2026 World Cup football match probabilities for engineering research, dashboard evidence, and paper-only tracking. It is not a betting system and must not be used to place real wagers.

Primary regulation-time outcomes:

- `home_win`
- `draw`
- `away_win`

Knockout workflows may also track `advance_result`, but that must be evaluated separately from the regulation 1X2 result.

## Intended Use

Allowed uses:

- pregame probability estimates
- fixture board evidence payloads
- historical evaluation
- calibration reports
- model-vs-market comparison as market consensus evidence
- paper-only tracking
- data-quality and source-health diagnostics

Disallowed uses:

- live betting
- automated wagering
- real-money betting
- real betting API integration
- pick submission to Tournamental or any external arena
- stake sizing
- claims of guaranteed profit

## Inputs

Core model features are governed by `scripts/football_feature_schema.py`. First-version core features are conservative pregame signals such as team-strength ratings, recent form, goal rates, and source-quality context.

Tracking-only or shadow features must not enter the active model without explicit schema promotion and tests. This includes market consensus, lineups, injuries, weather, news, xG, and Tournamental benchmark signals.

Every input row should retain source provenance and availability flags where possible.

## Outputs

Allowed prediction outputs include:

- fixture identifiers
- kickoff metadata
- home and away team names
- `model_home_prob`
- `model_draw_prob`
- `model_away_prob`
- model version
- feature schema hash
- source provenance
- explanation and evidence payloads
- safety flags locked false

Odds or market-derived fields may appear only as `market_consensus`, `external_signal`, or `paper_tracking` evidence.

## Evaluation

Evaluation is retrospective and sample-size gated.

Required evaluation metrics:

- multiclass Brier score
- multiclass LogLoss
- home/draw/away calibration
- group-stage vs knockout slices
- favorite vs underdog slices
- model-vs-market no-vig 1X2 comparison
- market movement / CLV-style evidence for paper tracking only

Low sample counts must report `insufficient_sample` instead of production readiness.

## Promotion Gates

Production-readiness claims are blocked when:

- `clean_train_samples < 300`
- `settled_predictions < 500`
- `production_samples < 1000`
- `feature_schema_hash` does not match
- model artifacts are missing or unloadable
- data contract checks fail
- any locked safety flag is true

Missing model artifacts must fall back to `manual_baseline` without crashing.

Allowed `model_source` values:

- `manual_baseline`
- `trained_artifact`
- `shadow_model`

## Limitations

- 2026 World Cup fixture data may be incomplete before official release windows.
- Provider schemas can change without notice.
- Weather, lineup, injury, and news context can be unavailable or stale.
- Market consensus can be missing, delayed, or biased by provider coverage.
- Draw probabilities need dedicated calibration because football is not a binary outcome.
- Knockout matches require separate handling for regulation result vs advancement.
- Historical open data may not represent current team strength.

## Safety Statement

The model is for analysis and paper tracking only. It must not output betting instructions, real-money wagering actions, or automated pick submissions. All external APIs must be read-only unless explicitly approved for a future non-betting use case.
