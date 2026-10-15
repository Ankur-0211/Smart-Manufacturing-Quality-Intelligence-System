"""Simulation routes (roadmap §9.3.2). Thin: validation + error mapping; logic lives in
``SimulationService``.

``POST /simulation/runs`` (run creation) is added once recipe validation exists; it needs the
shared contracts and the constraint-registry loader (R2-P1 tasks 9-10 / R2-P3).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse

from app.api.deps import DatabaseDep
from app.api.errors import ApiError, ErrorCode, build_meta
from app.api.sse import SSE_HEADERS, parse_last_event_id, run_event_stream
from app.db.errors import NotFoundError, RunImmutableError
from app.db.repositories import RunFilters
from app.engine.state_machine import InvalidTransitionError, RunImmutableTransitionError
from app.schemas.envelope import Envelope
from app.schemas.simulation import (
    AbortRequest,
    LabelRequest,
    OverrideRequest,
    ScenarioSummary,
    SimulationStateOut,
    StageNameLiteral,
    StartRequest,
)
from app.services.simulation_service import ExecutorUnavailableError, SimulationService

router = APIRouter(prefix="/simulation/runs", tags=["simulation"])


def simulation_service(request: Request) -> SimulationService:
    service: SimulationService = request.app.state.simulation
    return service


ServiceDep = Annotated[SimulationService, Depends(simulation_service)]


@contextmanager
def _mapped_errors(run_id: str | None = None) -> Iterator[None]:
    try:
        yield
    except NotFoundError as exc:
        raise ApiError(
            ErrorCode.RUN_NOT_FOUND, str(exc), field="run_id" if exc.entity == "run" else None
        ) from exc
    except (RunImmutableTransitionError, RunImmutableError) as exc:
        raise ApiError(
            ErrorCode.RUN_IMMUTABLE,
            str(exc),
            hint="Finished runs are immutable; re-run as a new run.",
        ) from exc
    except InvalidTransitionError as exc:
        raise ApiError(ErrorCode.INVALID_STATE_TRANSITION, str(exc)) from exc
    except ExecutorUnavailableError as exc:
        raise ApiError(
            ErrorCode.CAPABILITY_UNAVAILABLE,
            str(exc),
            hint="Simulation starts once the intelligence layer (mock or real) is wired in.",
        ) from exc


async def _state(
    request: Request, service: SimulationService, run_id: str
) -> Envelope[SimulationStateOut]:
    state = await run_in_threadpool(service.state, run_id)
    return Envelope(data=SimulationStateOut.model_validate(state), meta=build_meta(request))


async def _sync[T](fn: Callable[..., T], *args: Any) -> T:
    return await run_in_threadpool(fn, *args)


# ------------------------------------------------------------------ queries


@router.get("", response_model=Envelope[list[ScenarioSummary]], summary="Run history (paginated)")
async def list_runs(
    request: Request,
    service: ServiceDep,
    machine_id: str | None = None,
    product_id: str | None = None,
    material_lot_id: str | None = None,
    label: Literal["PASS", "FAIL"] | None = None,
    risk_level: Literal["NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"] | None = None,
    is_whatif: bool | None = None,
    inference_backend: Literal["real", "mock"] | None = None,
    created_from: Annotated[datetime | None, Query(alias="from")] = None,
    created_to: Annotated[datetime | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Envelope[list[ScenarioSummary]]:
    filters = RunFilters(
        machine_code=machine_id,
        product_code=product_id,
        material_lot_code=material_lot_id,
        is_whatif=is_whatif,
        inference_backend=inference_backend,
        created_from=created_from,
        created_to=created_to,
        label=label,
        risk_level=risk_level,
    )
    rows, total = await run_in_threadpool(
        lambda: service.list_runs(filters, limit=limit, offset=offset)
    )
    return Envelope(
        data=[ScenarioSummary.model_validate(r) for r in rows],
        meta=build_meta(request, total=total),
    )


@router.get(
    "/{run_id}", response_model=Envelope[SimulationStateOut], summary="Full SimulationState"
)
async def get_run(
    request: Request, run_id: str, service: ServiceDep
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        return await _state(request, service, run_id)


@router.get(
    "/{run_id}/stages/{stage}",
    response_model=Envelope[dict[str, Any]],
    summary="Single stage result",
)
async def get_stage(
    request: Request, run_id: str, stage: StageNameLiteral, service: ServiceDep
) -> Envelope[dict[str, Any]]:
    with _mapped_errors(run_id):
        data = await _sync(service.stage, run_id, stage)
    return Envelope(data=data, meta=build_meta(request))


@router.get(
    "/{run_id}/events",
    summary="Server-Sent Events stream of run events",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}}},
)
async def stream_events(
    request: Request,
    run_id: str,
    service: ServiceDep,
    database: DatabaseDep,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    with _mapped_errors(run_id):
        await _sync(service.ensure_run, run_id)
    keepalive: float = getattr(request.app.state, "sse_keepalive_s", 15.0)
    generator = run_event_stream(
        request,
        db=database,
        bus=service.bus,
        run_id=run_id,
        last_event_id=parse_last_event_id(last_event_id),
        keepalive_s=keepalive,
    )
    return StreamingResponse(generator, media_type="text/event-stream", headers=SSE_HEADERS)


# ------------------------------------------------------------------ commands


@router.post("/{run_id}/start", response_model=Envelope[SimulationStateOut])
async def start(
    request: Request, run_id: str, body: StartRequest, service: ServiceDep
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.start(run_id, mode=body.mode, speed_factor=body.speed_factor)
        return await _state(request, service, run_id)


@router.post("/{run_id}/advance", response_model=Envelope[SimulationStateOut])
async def advance(
    request: Request, run_id: str, service: ServiceDep
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.advance(run_id)
        return await _state(request, service, run_id)


@router.post("/{run_id}/pause", response_model=Envelope[SimulationStateOut])
async def pause(request: Request, run_id: str, service: ServiceDep) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.pause(run_id)
        return await _state(request, service, run_id)


@router.post("/{run_id}/resume", response_model=Envelope[SimulationStateOut])
async def resume(
    request: Request, run_id: str, service: ServiceDep
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.resume(run_id)
        return await _state(request, service, run_id)


@router.post("/{run_id}/reset", response_model=Envelope[SimulationStateOut])
async def reset(request: Request, run_id: str, service: ServiceDep) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.reset(run_id)
        return await _state(request, service, run_id)


@router.post("/{run_id}/abort", response_model=Envelope[SimulationStateOut])
async def abort(
    request: Request, run_id: str, service: ServiceDep, body: AbortRequest | None = None
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.abort(run_id, reason=body.reason if body else None)
        return await _state(request, service, run_id)


@router.post("/{run_id}/override", response_model=Envelope[SimulationStateOut])
async def override(
    request: Request, run_id: str, body: OverrideRequest, service: ServiceDep
) -> Envelope[SimulationStateOut]:
    with _mapped_errors(run_id):
        await service.override(run_id, stage=body.stage, acknowledgement=body.acknowledgement)
        return await _state(request, service, run_id)


@router.patch(
    "/{run_id}/label", response_model=Envelope[ScenarioSummary], summary="Save scenario label"
)
async def set_label(
    request: Request, run_id: str, body: LabelRequest, service: ServiceDep
) -> Envelope[ScenarioSummary]:
    with _mapped_errors(run_id):
        data = await _sync(service.set_label, run_id, body.scenario_label)
    return Envelope(data=ScenarioSummary.model_validate(data), meta=build_meta(request))
