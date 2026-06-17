# Data Layer

This folder is for reproducible local and generated data artifacts. Large raw datasets should not be committed unless they are small public fixtures or metadata snapshots.

## Suggested layout

```text
data/
  raw/          source API snapshots and immutable downloaded files
  interim/      normalized but not final records
  features/     model-ready feature tables
  external/     manually downloaded public datasets
```

## Source policy

- Public no-key sources can be snapshotted for validation.
- API keys must never be written to files in this repository.
- Live commercial APIs should be ingested through backend adapters and cached.
- Every generated file should include the source key, timestamp, and ingestion status.

## Current source registry

The authoritative source list lives in `backend/app/services/source_fusion_service.py`.

Current tiers:

1. Primary APIs: Zafronix, football-data.org, API-Football.
2. Public endpoints: World Cup 2026 public API, HumHub FWC 2026, ESPN scoreboard.
3. Open data: StatsBomb Open Data, OpenFootball worldcup.json, OpenFootball text data.
4. Research/backfill: soccerdata and GitHub scraper projects.
