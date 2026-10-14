# Architecture

The authoritative design is in `PROJECT_DEVELOPMENT_ROADMAP.md` §3 (architecture) and §9
(contracts). This file records **implementation** facts as they land, so it never duplicates or
contradicts the roadmap.

## Style

Modular monolith: one FastAPI process plus a React SPA. Intelligence is reached **in-process**
through `app.contracts.interface.QualityIntelligence` (roadmap §3.3). There are no microservices
and no message broker.

## Backend package map (implemented so far)

| Package | Owner | Status | Notes |
|---|---|---|---|
| `app/main.py` | R2 | done (R2-P1) | `create_app(settings)` factory. `/api/v1` prefix. OpenAPI at `/api/v1/openapi.json` |
| `app/core/config.py` | R2 | done | `SMQI_*` settings. Demo profile refuses non-`real` intelligence |
| `app/core/logging.py` | R2 | done | structlog JSON. `request_id` bound per request |
| `app/api/middleware.py` | R2 | done | Pure-ASGI request-ID middleware (SSE-safe) |
| `app/api/errors.py` | R2 | done | Stable error codes, `ApiError`, envelope handlers |
| `app/api/deps.py` | R2 | partial | Settings, Database, optional API key. Intelligence factory pending contracts |
| `app/api/routes_meta.py` | R2 | partial | `/health` done. `/constraints`, `/models` pending |
| `app/schemas/envelope.py` | R2 | done | `Envelope[T]`, `Meta`, `ErrorBody` |
| `app/contracts`, `app/domain` | R1 (joint) | awaited | R1-P1 |
| `app/intelligence_mock` | R2 | blocked | Needs contracts |
| `app/db` | R2 | done (R2-P2) | Models, Alembic `0001`, repositories, immutability guards, seed. See `database.md` |
| `app/engine`, `app/services` | R2 | not started | R2-P3…P5 |

## Request lifecycle

```
client -> RequestContextMiddleware (X-Request-ID, timing, structlog binding)
       -> CORSMiddleware
       -> router (optional X-API-Key dependency on protected routers; /health public)
       -> handler -> Envelope{data, error: null, meta}
errors -> ApiError | RequestValidationError | HTTPException | Exception
       -> register_exception_handlers -> Envelope{data: null, error, meta}
```

## Frontend map (implemented so far)

| Path | Status |
|---|---|
| `src/api/client.ts` | Envelope unwrap, `ApiClientError` (stable codes), `X-Request-ID` per request |
| `src/api/generated/schema.d.ts` | Generated from `docs/openapi.json`. Never hand-edited |
| `src/app/*` | Shell with 7 screens (placeholders), router, TanStack Query client |
| `src/components/common/Banners.tsx` | MOCK banner, API status, permanent simulation disclaimer |
| `src/test/*` | Vitest setup + MSW server. **Test-only** (an ESLint rule blocks `msw` imports in app code) |
