"""What-if and recommendation endpoints (roadmap 9.3.2; R2-P5 tasks 6-9). Thin routers."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from app.api.deps import IntelligenceDep, RegistryDep, SettingsDep
from app.api.errors import ApiError, ErrorCode, build_meta
from app.api.rate_limit import rate_limited
from app.api.routes_simulation import ServiceDep
from app.api.validation import validate_recipe
from app.contracts.sensitivity import SensitivityResult
from app.db.errors import NotFoundError
from app.schemas.envelope import Envelope
from app.schemas.whatif import (
    CompareRequest,
    RecommendOut,
    RecommendRequest,
    RunDiff,
    SensitivityRequest,
    WhatIfRequest,
    WhatIfResult,
)
from app.services.recommendation_service import RecommendationService
from app.services.simulation_service import ExecutorUnavailableError
from app.services.whatif_service import BaseNotFinalError, WhatIfService

router = APIRouter(tags=["what-if"])


@contextmanager
def _mapped(field: str) -> Iterator[None]:
    try:
        yield
    except NotFoundError as exc:
        raise ApiError(ErrorCode.RUN_NOT_FOUND, str(exc), field=field) from exc
    except BaseNotFinalError as exc:
        raise ApiError(
            ErrorCode.INVALID_STATE_TRANSITION,
            str(exc),
            field=field,
            hint="Finish the run (FINAL_RESULT) first.",
        ) from exc
    except ExecutorUnavailableError as exc:
        raise ApiError(ErrorCode.CAPABILITY_UNAVAILABLE, str(exc)) from exc


def _whatif(service: ServiceDep, registry: RegistryDep) -> WhatIfService:
    follows = bool(registry.recommendation_cfg.get("cycle_time_follows_stage_times", True))
    return WhatIfService(service, cycle_time_follows=follows)


@router.post(
    "/whatif",
    response_model=Envelope[WhatIfResult],
    summary="Branch a finished run: partial re-simulation of the invalidated stages + diff",
)
async def whatif(
    request: Request, body: WhatIfRequest, service: ServiceDep, registry: RegistryDep
) -> Envelope[WhatIfResult]:
    def validate(recipe: Mapping[str, float], context: Mapping[str, Any]) -> dict[str, float]:
        return validate_recipe(registry, recipe, context=context, loc="overrides")

    whatifs = _whatif(service, registry)
    with _mapped("base_run_id"):
        result = await run_in_threadpool(
            lambda: whatifs.evaluate(
                body.base_run_id,
                body.overrides,
                validate=validate,
                persist=body.persist,
                label=body.label,
            )
        )
    return Envelope(data=WhatIfResult.model_validate(result), meta=build_meta(request))


@router.post(
    "/whatif/compare", response_model=Envelope[RunDiff], summary="Diff between two finished runs"
)
async def compare(
    request: Request, body: CompareRequest, service: ServiceDep, registry: RegistryDep
) -> Envelope[RunDiff]:
    whatifs = _whatif(service, registry)
    with _mapped("run_id_a"):
        diff = await run_in_threadpool(whatifs.compare, body.run_id_a, body.run_id_b)
    return Envelope(data=RunDiff.model_validate(diff), meta=build_meta(request))


@router.post(
    "/whatif/sensitivity",
    response_model=Envelope[SensitivityResult],
    summary="1-D sensitivity sweep around a finished run",
    dependencies=[Depends(rate_limited("sensitivity"))],
)
async def sensitivity(
    request: Request,
    body: SensitivityRequest,
    service: ServiceDep,
    registry: RegistryDep,
    intelligence: IntelligenceDep,
) -> Envelope[SensitivityResult]:
    whatifs = _whatif(service, registry)
    with _mapped("base_run_id"):
        result = await run_in_threadpool(
            whatifs.sensitivity, body.base_run_id, body.parameter, body.steps, intelligence
        )
    return Envelope(data=result, meta=build_meta(request))


@router.post(
    "/recommend",
    response_model=Envelope[RecommendOut],
    summary="Constrained recommendations for a finished run (model-relative, guarded)",
    dependencies=[Depends(rate_limited("recommend"))],
)
async def recommend(
    request: Request,
    body: RecommendRequest,
    service: ServiceDep,
    intelligence: IntelligenceDep,
    settings: SettingsDep,
) -> Envelope[RecommendOut]:
    recommender = RecommendationService(service.db, intelligence)
    with _mapped("run_id"):
        result = await run_in_threadpool(
            lambda: recommender.recommend(
                body.run_id,
                locked=body.locked,
                max_changes=body.max_changes,
                n_options=body.n_options,
                objective=body.objective,
                enable_refinement=body.enable_refinement,
                time_budget_s=settings.recommend_time_budget_s,
            )
        )
    return Envelope(data=RecommendOut.model_validate(result), meta=build_meta(request))
