# Football Prediction Analytics Technical Blueprint

This document turns the working project direction into an implementation blueprint. It is intentionally conservative: claims that require verified historical data, tracking data, or backtesting are treated as hypotheses until measured.

## Product goal

Build a football analytics platform with:

- Live and scheduled match data.
- AI win/draw/loss probability.
- Market-consensus signal from The Odds API.
- Advanced model feature registry.
- Feature-table generation for reproducible model evidence.
- Future real-time event updates through WebSocket.

The product is an analysis and prediction platform. It does not place bets or execute betting actions.

## Current implemented foundation

- FastAPI backend.
- Next.js frontend.
- Source registry with public, premium, open-data, and market-signal sources.
- The Odds API settings and runtime client.
- `/odds/sports`, `/odds/upcoming`, and `/odds/market-consensus` endpoints.
- Advanced model feature registry.
- Match feature-table service and validation workflow.

## Source strategy

| Tier | Sources | Current status | Usage |
| --- | --- | --- | --- |
| Fixture truth | football-data.org, API-Football, Zafronix | Configurable | Fixtures, results, standings, teams |
| Public fallback | ESPN scoreboard, World Cup 2026 public API, HumHub FWC 2026 | Partially configured | Fallback snapshots and schedule checks |
| Open training data | StatsBomb Open Data, OpenFootball | Registered | Offline model training and regression checks |
| Market signal | The Odds API | Adapter implemented | H2H market consensus and implied probability |
| Research/backfill | soccerdata, GitHub scraper projects | Registered | Offline research and backfill only |

## Six-layer target architecture

### Layer 1: Data pipeline

Target components:

- Fetchers/adapters for each source.
- Retry and timeout handling.
- Raw snapshots under `data/raw`.
- Normalized records under `data/interim`.
- Feature rows under `data/features`.

Near-term implementation should avoid heavy queue infrastructure until there is enough ingestion volume. Start with scripts and CI reports, then graduate to Celery Beat when ingestion cadence requires scheduled workers.

### Layer 2: Storage and cache

Target components:

- PostgreSQL for structured entities.
- Redis for API/result cache.
- TimescaleDB only when minute-by-minute event streams are available.
- Object storage for model artifacts, badges, and large static files.

Current MVP can continue using generated JSON artifacts until ingestion proves stable.

### Layer 3: Backend API

Target components:

- FastAPI app split into routers.
- Source router.
- Fixture router.
- Prediction router.
- Odds router.
- Feature table router.
- Future database session and repository layer.

### Layer 4: Real-time layer

Target components:

- FastAPI WebSocket endpoint.
- Redis Pub/Sub for event fanout.
- Live match updates such as goals, red cards, substitutions, and market-move alerts.

Real-time should be added after reliable ingestion exists.

### Layer 5: Frontend

Target components:

- Match cards.
- Prediction panel.
- Source status panel.
- Market signal panel.
- xG/xT visualization.
- Fixture filters.
- Team pages.
- Article/explainer pages.

### Layer 6: DevOps

Target components:

- GitHub Actions validation.
- Render backend deployment.
- Vercel frontend deployment.
- Future Docker Compose for local PostgreSQL and Redis.
- Future observability for API quota and source failures.

## Advanced model feature roadmap

| Feature | Status | Notes |
| --- | --- | --- |
| Elo / team strength | Implemented baseline | Already in feature table |
| Attack-defense split | Planned | Derive from goals, xG, and conceded quality |
| xG/xT profile | Requires event data | StatsBomb can seed offline training |
| Player availability/load | Requires lineup/injury source | Must respect prediction cutoff time |
| Referee/card profile | Planned | Requires referee assignments and historical card rates |
| Weather/venue context | Planned | Do not hardcode environment coefficients without backtest |
| Market consensus | Adapter implemented | The Odds API h2h consensus becomes model input |
| Spatial unpredictability | Research | Requires event/tracking coordinates |
| Video micro-features | Future research | Requires video/tracking pipeline |
| Bayesian uncertainty | Planned model layer | For calibrated confidence and intervals |
| Ensemble stack | Planned model layer | Poisson + rating + tree models + calibration |
| Incremental learning | Future research | Only after backtest framework exists |
| Draw specialist | Planned | Draws need dedicated calibration |

## Leakage policy

- Scheduled fixture feature rows must use only pre-match information.
- Final scores are targets only, not model inputs.
- Closing odds cannot be mixed into historical training unless the prediction cutoff is explicitly modeled.
- Injury, lineup, referee, weather, and odds features must include timestamp and source metadata.

## MVP priority after The Odds API adapter

1. Verify `/odds/sports` and identify football sport keys.
2. Query `/odds/market-consensus` for soccer sport keys.
3. Persist market-consensus summary into `data/features/match_features.json`.
4. Add frontend market-signal display.
5. Create local Docker Compose for PostgreSQL + Redis.
6. Split backend into routers after API surface stabilizes.
7. Add ingestion adapter base class for OpenFootball, ESPN, and The Odds API.
