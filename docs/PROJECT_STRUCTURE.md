# Football Prediction Project Structure

This repository follows a product + model engineering layout inspired by mature football prediction projects:

```text
backend/     FastAPI API, prediction service, source registry, model service
frontend/    Next.js public website and football intelligence portal
data/        local development datasets and generated feature snapshots
scripts/     repeatable ingestion, validation, training, and reporting commands
tests/       unit and integration tests for source registry, fixtures, and predictions
report/      generated validation reports, model cards, and data-quality summaries
docs/        architecture, API design, and operating notes
.github/     CI workflows for validation before deployment
```

## Data flow

```text
public / premium sources
  -> source adapters
  -> normalized fixture/team/event records
  -> feature table
  -> prediction model
  -> FastAPI endpoints
  -> Next.js football portal
```

## Source tiers

1. Primary API sources: football-data.org, API-Football, Zafronix when available.
2. Public no-key sources: World Cup 2026 API, OpenFootball, ESPN scoreboard, HumHub if validated.
3. Open training data: StatsBomb Open Data and historical OpenFootball data.
4. Research and backfill tools: soccerdata and GitHub scraper projects.

## Operating rule

No API keys are committed to GitHub. Secrets live in Render environment variables. Public URLs and no-key source defaults can be committed when they are not credentials.
