"""FastAPI application factory (roadmap Section 3, R2-P1).

Run with:
    uv run uvicorn app.main:app --reload --app-dir backend --port 8000
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes_meta, routes_reference, routes_simulation
from app.api.deps import build_intelligence, require_api_key
from app.api.errors import register_exception_handlers
from app.api.middleware import RequestContextMiddleware
from app.api.rate_limit import TokenBucketLimiter
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import Database
from app.domain.constraint_loader import ConstraintRegistry
from app.engine.cache import StageCache
from app.engine.events import EventBus
from app.services.intelligence_executor import IntelligenceStageExecutor
from app.services.simulation_service import SimulationService

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)
    log = get_logger("app.startup")

    # Startup order (roadmap R2-P1 task 3): settings -> registry -> intelligence -> DB.
    # An invalid registry or an unavailable `real` backend raises here, so the app never starts.
    registry = ConstraintRegistry.load(settings.constraints_path)
    intelligence = build_intelligence(settings, registry)
    executor = IntelligenceStageExecutor(intelligence, registry)
    database = Database(settings.database_url)
    simulation = SimulationService(
        database,
        EventBus(),
        StageCache(settings.stage_cache_size),
        executor=executor,
        stage_presentation_ms=settings.stage_presentation_ms,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        db_status = database.status()
        info = intelligence.version_info()
        log.info(
            "startup",
            env=settings.env.value,
            intelligence_backend=settings.intelligence_backend.value,
            inference_backend=info.inference_backend.value,
            is_mock=info.is_mock,
            constraints_version=registry.version,
            constraints_hash=registry.content_hash[:12],
            database_url_scheme=settings.database_url.split(":", 1)[0],
            db_reachable=db_status.reachable,
            db_revision=db_status.revision,
            db_head=db_status.head,
        )
        if db_status.migrated:
            recovered = simulation.recover_interrupted()
            if recovered:
                log.warning("runs_aborted_after_restart", run_ids=recovered)
        else:
            log.warning("database_not_migrated", detail=db_status.detail)
        yield
        await simulation.shutdown()
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
    app.state.registry = registry
    app.state.intelligence = intelligence
    app.state.simulation = simulation
    app.state.sse_keepalive_s = 15.0
    app.state.rate_limiter = TokenBucketLimiter(settings.rate_limit_per_min)

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
PROTECTED_ROUTERS: list[APIRouter] = [routes_reference.router, routes_simulation.router]


def include_protected(app: FastAPI, router: APIRouter) -> None:
    """Mount a router under /api/v1 behind the optional X-API-Key check."""
    app.include_router(router, prefix=API_PREFIX, dependencies=[Depends(require_api_key)])


app = create_app()
