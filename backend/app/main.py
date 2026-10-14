"""FastAPI application factory (roadmap Section 3, R2-P1).

Run with:
    uv run uvicorn app.main:app --reload --app-dir backend --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_meta
from app.api.deps import require_api_key
from app.api.errors import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import Database

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    log = get_logger("app.startup")

    database = Database(settings.database_url)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Startup order (roadmap R2-P1 task 3): settings -> registry -> intelligence -> DB.
        # Registry and intelligence are wired once Role 1 contracts exist.
        db_status = database.status()
        log.info(
            "startup",
            env=settings.env.value,
            intelligence_backend=settings.intelligence_backend.value,
            database_url_scheme=settings.database_url.split(":", 1)[0],
            db_reachable=db_status.reachable,
            db_revision=db_status.revision,
            db_head=db_status.head,
        )
        if not db_status.migrated:
            log.warning("database_not_migrated", detail=db_status.detail)
        yield
        database.dispose()
        log.info("shutdown")

    app = FastAPI(
        title="Smart Manufacturing Quality Intelligence API",
        version="0.1.0",
        description=(
            "Software-level process simulation and decision support for PP injection "
            "molding. It does not solve polymer physics; predictions are statistical "
            "and recommendations are model-relative."
        ),
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = database

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID", "X-API-Key", "Last-Event-ID"],
        expose_headers=["X-Request-ID"],
    )
    # Added last so it wraps everything (including CORS) and sees every request.
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    # /health stays reachable without an API key (liveness probes); everything else is guarded.
    app.include_router(routes_meta.router, prefix=API_PREFIX)
    for router in PROTECTED_ROUTERS:
        include_protected(app, router)

    return app


# Feature routers (simulation, predict, whatif, ...) are registered here in later phases.
PROTECTED_ROUTERS: list[APIRouter] = []


def include_protected(app: FastAPI, router: APIRouter) -> None:
    """Mount a router under /api/v1 behind the optional X-API-Key check."""
    app.include_router(router, prefix=API_PREFIX, dependencies=[Depends(require_api_key)])


app = create_app()
