# Troubleshooting (roadmap R2-P9 task 8)

## Port already in use

`uvicorn` fails with "address already in use" (Windows: error 10048), or `npm run dev` stops with "Port 5173 is already in use" (the dev server uses `strictPort`).

- Find the process. On Windows: `Get-NetTCPConnection -LocalPort 8000 -State Listen` gives an `OwningProcess` to stop. On Unix: `lsof -i :8000`.
- Or start on another port: `--port 8010`. In dev, also point the SPA at it with `VITE_API_BASE_URL=http://localhost:8010/api/v1` in `frontend/.env.local`.

## The header shows "API: unreachable", or the console shows CORS errors

- In dev the SPA calls `http://localhost:8000/api/v1`, and the API only allows origins listed in `SMQI_CORS_ORIGINS` (default `http://localhost:5173`).
- In the demo profile, open the app on the API's own port (`http://localhost:8000/`). It is then same-origin, so CORS does not apply.

## Live updates stall (SSE behind a proxy)

The run view streams `/simulation/runs/{id}/events` as Server-Sent Events and falls back to polling
when the stream drops.

- A buffering proxy delays events until its buffer fills. Disable response buffering for that path. The API already sends `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
- Keepalives come every 15 s. Proxy idle timeouts must be longer than that.

## Constraints version mismatch

`/health` and the startup log show `constraints_version` and a content hash.

- A prediction made under another registry version is still shown, with the version it used.
- A what-if reuses stored stages only when the limits version **and** the model version match the parent. Otherwise every stage is recomputed.
- After Role 1 changes `constraints.yaml`, restart the API. The SPA picks up the new `GET /constraints` through its ETag.

## Model bundle hash mismatch

Not applicable yet: Role 1's `fusion-1.0.0` loads no bundle (see `deployment.md`). Once there is a
bundle, a hash that disagrees with `models/MANIFEST.sha256` means the archive was modified or
partially extracted. Re-extract it; never edit artifacts locally.

## Python version

- `uv sync --frozen` uses Python 3.12 from `.python-version` (UD-01), even if the machine default is 3.14.
- `ModuleNotFoundError: app` means the command did not run through `uv run`, or ran outside the repository root. `uv run` installs the project, so `uv run python -m app.db.seed` works from the root.
- A stale `.venv` created by another Python: delete `.venv`, then run `uv sync --frozen`.

## Windows specifics

- **Paths:** settings that take paths (`SMQI_MODEL_DIR`, `SMQI_CONSTRAINTS_PATH`, `SMQI_FLEET_PATH`, `SMQI_FRONTEND_DIST`) resolve relative to the repository root, not the current folder. SQLite URLs use forward slashes: `sqlite:///C:/path/to/smqi.db`.
- **Console encoding:** scripts that print symbols (`scripts/benchmark.py`) switch stdout to UTF-8 themselves. For other tools, run `chcp 65001` or set `PYTHONIOENCODING=utf-8`.
- **Line endings:** `.gitattributes` forces LF. If Git warns about CRLF, keep the repository settings and do not set `core.autocrlf=true` for this clone.
- **Environment variables:** PowerShell uses `$env:SMQI_ENV = "demo"`, not `export`.

## Database

- "no such table": run `uv run alembic -c backend/alembic.ini upgrade head`. The startup log shows `db_revision` and `db_head`, and they must match.
- An empty machine, product or lot picker: run `uv run python -m app.db.seed` (it reads `backend/app/domain/fleet.yaml`).
- `seed_demo_runs.py` refuses to run while the API serves MOCK intelligence; restart the API with `SMQI_INTELLIGENCE_BACKEND=real`.

## Known issues

These are open with Role 1 (details in `contract_changes/CCR-004-role1-integration-findings.md`):

- The 4-cavity product is always BLOCKED (#1), and MC-03 can't run the nominal recipe (#7).
- Recommendations can predict no gain (#7a), and the step-size guard passes oversized steps (#7b). The UI flags the latter.
- `flip_point` is the first crossing, not the nearest one (#7c).
- Model Info shows "not reported" for metrics and provenance (#7d).
- No SPC alerts (#10).
- `stage_risk_mass` doesn't always sum to 1 (#3), so the risk origin can read 20 % per stage.
