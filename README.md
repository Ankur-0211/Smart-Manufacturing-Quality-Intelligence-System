# Smart Manufacturing Quality Intelligence System

Software-level process simulation, calibrated quality prediction, explanation and constrained
recommendation for **polypropylene (PP) injection molding** of a 30–60 g electrical junction-box
housing.

> This system performs a **software-level** process simulation. It does not solve polymer physics.
> Predictions are statistical, and recommendations are **model-relative**, not plant-validated.
> See `PROJECT_DEVELOPMENT_ROADMAP.md` §1.7.

- **Single source of truth:** [`PROJECT_DEVELOPMENT_ROADMAP.md`](PROJECT_DEVELOPMENT_ROADMAP.md)
- **Design baseline:** `Smart_Manufacturing_Quality_Intelligence_Project_Plan.pdf`
- **Integration status (what is real vs mock):** [`docs/integration_status.md`](docs/integration_status.md)

## Repository layout (roadmap §4)

| Path | Owner | Purpose |
|---|---|---|
| `backend/app/api`, `schemas`, `services`, `engine`, `db`, `core`, `intelligence_mock` | Role 2 | FastAPI app, simulation engine, persistence |
| `backend/app/contracts`, `domain` | Joint (Role 1 authors) | Shared types, constraint registry |
| `backend/app/intelligence`, `ml`, `recommendation`, `ml_pipeline/` | Role 1 | Stage intelligence, models, recommendations |
| `frontend/` | Role 2 | React 18 + TypeScript SPA |
| `docs/` | Both | Architecture, API, events, contracts, decisions |

## Prerequisites

- [uv](https://docs.astral.sh/uv/) 0.10+. It provisions **Python 3.12** from `.python-version`.
- Node.js 24 and npm 11.

## Backend

```bash
uv sync --frozen                     # Role 1 adds: --group ml
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.db.seed         # needs backend/app/domain/fleet.yaml (Role 1)
uv run uvicorn app.main:app --reload --app-dir backend --port 8000
```

Database details are in [`docs/database.md`](docs/database.md).

- API docs: <http://localhost:8000/api/v1/docs>
- Health: <http://localhost:8000/api/v1/health>

Configuration comes from environment variables with the `SMQI_` prefix. Copy `.env.example` to
`.env` to override them. In PowerShell, set a variable for the current session with
`$env:SMQI_LOG_FORMAT = "console"`.

## Frontend

```bash
cd frontend
npm ci
npm run dev          # http://localhost:5173
```

## Checks

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
npm run test:e2e     # Playwright: builds, starts scripts/e2e_server.py on :8001 (fresh DB, real intelligence)
```

The first E2E run on a machine needs the browser once: `npx playwright install chromium`.

## Regenerating API types

The frontend never hand-writes API types (roadmap §9.3.1). After any backend API change, run one
of these and commit `docs/openapi.json` together with
`frontend/src/api/generated/schema.d.ts`:

```bash
sh scripts/gen_api_types.sh          # or: powershell -File scripts/gen_api_types.ps1
```

## Demo profile (roadmap §16.2)

The demo runs on Role 1's real intelligence only; `SMQI_ENV=demo` refuses `mock` and `hybrid`.

```bash
# bash; in PowerShell set $env:SMQI_ENV = "demo" etc.
export SMQI_ENV=demo SMQI_INTELLIGENCE_BACKEND=real
uv run alembic -c backend/alembic.ini upgrade head
(cd backend && uv run python -m app.db.seed)
uv run uvicorn app.main:app --app-dir backend --port 8000
```

In a second terminal, while the API is running:

```bash
uv run python scripts/seed_demo_runs.py
```

This creates four runs **through the API**, using the contract-fixture recipes on MC-02 / PP-JBOX-42:

| Scenario | Lot | Outcome |
|---|---|---|
| Nominal recipe | A-771 | PASS |
| Short cooling | A-771 | PASS, with an HC-004 warning |
| High injection pressure (nominal + 1800 bar) | A-771 | FAIL 0.59, operational risk HIGH, anomaly on Injection; a what-if at 1100 bar flips it to PASS |
| Melt above ceiling | A-771 | Left **BLOCKED** at Plasticizing (HC-001), so the override can be shown live; the result is then NOT RELEASABLE |

Re-running the script skips scenarios that already exist.

The `D-105` lot is wet: any run on it blocks at Material Conditioning (HC-006). MC-03 can't run the nominal recipe, because its 110 t clamp rating is below the nominal 120 t (coupling rule CPL-003).

## Single-process deployment and troubleshooting

For the demo machine, build the frontend once (`cd frontend && npm run build`). The API then serves
it at <http://localhost:8000/> together with `/api/v1`, on one origin. The steps are in
[`docs/deployment.md`](docs/deployment.md), common problems in
[`docs/troubleshooting.md`](docs/troubleshooting.md), and the performance check is
`uv run python scripts/benchmark.py`. Test results are in [`docs/system_test_report.md`](docs/system_test_report.md).

## Branches (roadmap §14)

| Branch | Purpose |
|---|---|
| `main` | Integration branch, always runnable |
| `role-1-ai-ml` | Role 1 work |
| `role-2-application` | Role 2 work |

Merge to `main` only through PRs with all checks green.
