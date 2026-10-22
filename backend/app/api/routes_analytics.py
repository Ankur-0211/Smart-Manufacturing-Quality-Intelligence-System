"""Analytics endpoints (roadmap 9.3.2; R2-P8 tasks 3 and 5). Thin: SQL lives in AnalyticsService."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.api.deps import DatabaseDep, RegistryDep
from app.api.errors import ApiError, ErrorCode, build_meta
from app.db.errors import NotFoundError
from app.db.repositories import ReferenceRepository
from app.schemas.analytics import (
    AnalyticsSummary,
    GroupedAnalytics,
    MaterialAnalytics,
    ParameterAnalytics,
    SpcOut,
)
from app.schemas.envelope import Envelope
from app.services.analytics_service import (
    AnalyticsFilters,
    AnalyticsService,
    UnknownParameterError,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Role 1's Protocol has no spc_check(SpcSeries) and the contracts no SpcSeries/SpcAlert yet
# (CCR-004 #10), so alerts cannot be requested. Role 2 does not implement SPC rules itself.
SPC_UNAVAILABLE = (
    "SPC alerts come from the intelligence layer's spc_check, which Role 1 has not delivered yet "
    "(CCR-004 #10). The stored series is shown without control limits."
)


def filters(
    include_whatif: bool = False,
    include_mock: bool = False,
    include_unfinished: bool = False,
    created_from: Annotated[datetime | None, Query(alias="from")] = None,
    created_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> AnalyticsFilters:
    return AnalyticsFilters(
        include_whatif=include_whatif,
        include_mock=include_mock,
        include_unfinished=include_unfinished,
        created_from=created_from,
        created_to=created_to,
    )


FiltersDep = Annotated[AnalyticsFilters, Depends(filters)]


def _parameter_spec(registry: Any, parameter: str) -> dict[str, Any]:
    spec = registry.parameters.get(parameter)
    if spec is None or spec.get("min") is None or spec.get("max") is None:
        raise ApiError(
            ErrorCode.UNKNOWN_PARAMETER,
            f"{parameter!r} is not a registry parameter with a window",
            field="parameter",
        )
    return dict(spec)


@router.get(
    "/summary",
    response_model=Envelope[AnalyticsSummary],
    summary="Run counts, predicted FAIL share, stage risk frequency",
)
async def summary(
    request: Request, database: DatabaseDep, f: FiltersDep
) -> Envelope[AnalyticsSummary]:
    data = await run_in_threadpool(AnalyticsService(database).summary, f)
    return Envelope(data=AnalyticsSummary.model_validate(data), meta=build_meta(request))


@router.get(
    "/by-machine", response_model=Envelope[GroupedAnalytics], summary="Outcomes per machine"
)
async def by_machine(
    request: Request, database: DatabaseDep, f: FiltersDep
) -> Envelope[GroupedAnalytics]:
    data = await run_in_threadpool(AnalyticsService(database).by_machine, f)
    return Envelope(data=GroupedAnalytics.model_validate(data), meta=build_meta(request))


@router.get(
    "/by-material",
    response_model=Envelope[MaterialAnalytics],
    summary="Outcomes per material lot or resin grade",
)
async def by_material(
    request: Request,
    database: DatabaseDep,
    f: FiltersDep,
    group: Literal["lot", "resin_grade"] = "lot",
) -> Envelope[MaterialAnalytics]:
    data = await run_in_threadpool(AnalyticsService(database).by_material, f, group)
    return Envelope(data=MaterialAnalytics.model_validate(data), meta=build_meta(request))


@router.get(
    "/by-parameter",
    response_model=Envelope[ParameterAnalytics],
    summary="Outcomes per equal-width bucket of a parameter's registry window",
)
async def by_parameter(
    request: Request,
    database: DatabaseDep,
    registry: RegistryDep,
    f: FiltersDep,
    parameter: str,
    buckets: Annotated[int, Query(ge=2, le=20)] = 5,
) -> Envelope[ParameterAnalytics]:
    spec = _parameter_spec(registry, parameter)
    try:
        data = await run_in_threadpool(
            AnalyticsService(database).by_parameter, f, parameter, buckets, spec
        )
    except UnknownParameterError as exc:
        raise ApiError(ErrorCode.UNKNOWN_PARAMETER, str(exc), field="parameter") from exc
    return Envelope(data=ParameterAnalytics.model_validate(data), meta=build_meta(request))


@router.get(
    "/spc", response_model=Envelope[SpcOut], summary="A parameter's stored series on one machine"
)
async def spc(
    request: Request,
    database: DatabaseDep,
    registry: RegistryDep,
    f: FiltersDep,
    machine_id: str,
    parameter: str,
    limit: Annotated[int, Query(ge=2, le=500)] = 100,
) -> Envelope[SpcOut]:
    spec = _parameter_spec(registry, parameter)

    def load() -> list[dict[str, Any]]:
        with database.session() as s:
            try:
                ReferenceRepository(s).machine(machine_id)
            except NotFoundError as exc:
                raise ApiError(ErrorCode.REFERENCE_NOT_FOUND, str(exc), field="machine_id") from exc
        try:
            return AnalyticsService(database).spc_series(f, machine_id, parameter, limit)
        except UnknownParameterError as exc:
            raise ApiError(ErrorCode.UNKNOWN_PARAMETER, str(exc), field="parameter") from exc

    series = await run_in_threadpool(load)
    data = {
        "machine_id": machine_id,
        "parameter": parameter,
        "unit": spec.get("unit"),
        "filters": f,
        "series": series,
        "spc": {"available": False, "reason": SPC_UNAVAILABLE},
        "alerts": None,
    }
    return Envelope(
        data=SpcOut.model_validate(data, from_attributes=True), meta=build_meta(request)
    )
