# Runtime Deployment Checklist

This checklist verifies that the deployed football platform has a reachable backend runtime and that public health endpoints return JSON without exposing secrets or enabling betting behavior.

## Deployment URLs

| Item | Value |
| --- | --- |
| Frontend URL | Set after Vercel deployment, for example `https://<vercel-project>.vercel.app` |
| Backend URL | Set after Render deployment, for example `https://<render-service>.onrender.com` |
| Runtime smoke env | `FOOTBALL_BACKEND_URL=<backend URL>` |

Do not commit actual private service URLs if they encode secrets, preview tokens, or protected deployment credentials.

## Required Public Backend Endpoints

The backend runtime must return JSON for these public endpoints:

| Endpoint | Expected behavior |
| --- | --- |
| `/health` | Returns application health and model version. |
| `/data-sources` | Returns the public canonical 13-source registry mapped to API status fields. |
| `/data-sources/canonical` | Returns canonical source metadata without API key values. |
| `/ingestion/fixtures` | Returns a JSON ingestion report even when providers are disabled, missing keys, rate limited, unavailable, or mismatched. |
| `/fixtures` | Returns cached or demo fixture JSON without requiring external provider keys. |

## Render Backend Service

Recommended Render service shape:

- Service type: Web Service.
- Runtime: Python 3.11 or compatible.
- Build command: install `backend/requirements.txt`.
- Start command: run FastAPI with `uvicorn app.main:app` from the `backend` directory.
- Health check path: `/health`.
- Environment variables: configure provider keys only in Render Environment Variables.
- Safety env defaults:
  - `LIVE_BETTING_ALLOWED=false`
  - `AUTOMATED_WAGERING_ALLOWED=false`
  - `REAL_MONEY_BETTING_ALLOWED=false`
  - `TOURNAMENTAL_ENABLE_PICK_SUBMISSION=false`

For runtime smoke checks, set `FOOTBALL_BACKEND_URL` locally or in CI to the public Render backend base URL.

## Vercel Frontend

The frontend should know the backend base URL through `NEXT_PUBLIC_API_BASE_URL`.

If the frontend calls backend endpoints directly from browser code, set:

```text
NEXT_PUBLIC_API_BASE_URL=https://<render-service>.onrender.com
```

If the frontend should use same-origin API paths, add an explicit Vercel rewrite from frontend routes such as `/api/backend/:path*` to the Render backend. Do not assume Vercel will proxy FastAPI endpoints automatically. Confirm whether the deployed frontend needs this before changing routing.

## Runtime Smoke Check

Run from the repository root:

```bash
FOOTBALL_BACKEND_URL=https://<render-service>.onrender.com python scripts/runtime_smoke_check.py
```

If `FOOTBALL_BACKEND_URL` is missing, the script must not crash. It should print a JSON report with `status` set to `missing_backend_url`.

A healthy backend should produce a report with:

- `status`: `ok`
- one endpoint result per required endpoint
- each endpoint result has `attempted=true`, `success=true`, and a 2xx `status_code`
- no API keys, tokens, or secrets in the report

## Secret Leak Check

Confirm that runtime output does not contain:

- provider API key values
- bearer tokens
- query parameters such as `api_key`, `token`, `access_token`, or `subscription-key`
- `recommended_bet`
- `stake_size`

The runtime smoke report redacts sensitive URL query parameters and known secret-like environment values from errors before printing JSON.

## Live Betting Locked Check

Confirm these remain false in deployment settings, generated reports, and API payloads:

- `live_betting_allowed`
- `automated_wagering_allowed`
- `real_money_betting_allowed`
- `pick_submission_allowed`
- `TOURNAMENTAL_ENABLE_PICK_SUBMISSION`

The runtime check is read-only. It must not call real betting APIs, submit picks, size stakes, or enable live betting.