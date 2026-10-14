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
uv run uvicorn app.main:app --reload --app-dir backend --port 8000
```

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
uv run black --check .
uv run mypy
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm test
npm run build
```

## Regenerating API types

The frontend never hand-writes API types (roadmap §9.3.1). After any backend API change, run one
of these and commit `docs/openapi.json` together with
`frontend/src/api/generated/schema.d.ts`:

```bash
sh scripts/gen_api_types.sh          # or: powershell -File scripts/gen_api_types.ps1
```

## Branches (roadmap §14)

| Branch | Purpose |
|---|---|
| `main` | Integration branch, always runnable |
| `role-1-ai-ml` | Role 1 work |
| `role-2-application` | Role 2 work |

Merge to `main` only through PRs with all checks green.
