# Deployment (roadmap R2-P9)

The primary deployment is **local, single process**: FastAPI serves the API at `/api/v1` and the
built SPA at `/` (UD-16). There is one origin, so no CORS setup is needed. Docker Compose and CI are
P2 and not built.

## Demo machine, from a clean clone

Prerequisites: [uv](https://docs.astral.sh/uv/) 0.10+ (it provisions Python 3.12), Node.js 24 with
npm 11, and Git.

```bash
git clone --branch role-2-application https://github.com/Ankur-0211/Smart-Manufacturing-Quality-Intelligence-System.git
cd Smart-Manufacturing-Quality-Intelligence-System
uv sync --frozen
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.db.seed
cd frontend && npm ci && npm run build && cd ..
```

Start the API in the demo profile. It serves `frontend/dist` because that folder now holds `index.html`.

```bash
# bash
SMQI_ENV=demo SMQI_INTELLIGENCE_BACKEND=real uv run uvicorn app.main:app --app-dir backend --port 8000
```

```powershell
# PowerShell
$env:SMQI_ENV = "demo"; $env:SMQI_INTELLIGENCE_BACKEND = "real"
uv run uvicorn app.main:app --app-dir backend --port 8000
```

In a second terminal, seed the demo history through the API:

```bash
uv run python scripts/seed_demo_runs.py --base-url http://localhost:8000
```

Then open <http://localhost:8000/>.

### What to check

- `GET /api/v1/health`: `status` is `ok`, `intelligence.is_mock` is `false`, and `model_version` is `fusion-1.0.0`.
- The `startup` log line lists everything that was resolved: env, backend, model version, contracts version, capabilities, constraints version and hash, DB revision and head, and the served frontend folder.
- `SMQI_ENV=demo` refuses `mock` and `hybrid` (the process exits at startup).

## Profiles

| | dev | demo |
|---|---|---|
| Intelligence | `real` by default; `mock`/`hybrid` allowed | `real` only |
| Frontend | Vite dev server on :5173, API on :8000 | `frontend/dist` served by the API on :8000 |
| API base used by the SPA | `http://localhost:8000/api/v1` | same-origin `/api/v1` (production build default) |
| Presentation speed | per run (default 1x) | per run (default 1x) |
| `X-API-Key` | optional (`SMQI_API_KEY`) | optional |

`VITE_API_BASE_URL`, if set at build time, overrides the SPA's API base in either profile.

## Performance (Plan §24.4)

`uv run python scripts/benchmark.py` builds the app on a temporary database with the real
intelligence and prints p50/p95/max for each budgeted operation, both in the intelligence layer and
end to end through the API. Record each run in `integration_status.md` with the date and machine.

## Model artifacts

Role 1's current facade (`fusion-1.0.0`) is pure Python and loads **no** model bundle, so there is
no `models/` directory, no `MANIFEST.sha256` to verify, and no missing-bundle failure to test yet
(roadmap R2-P9 task 1). Once Role 1 publishes the archive (roadmap §14.5): unpack it to `models/`,
verify `MANIFEST.sha256`, and start with `SMQI_ENV=demo`. Artifacts are used exactly as published,
with no local edits (R2-P9 §15).

## Not built (P2)

- `docker/` (Compose with api, PostgreSQL and web) and migrations on PostgreSQL.
- `.github/workflows/ci.yml`.
