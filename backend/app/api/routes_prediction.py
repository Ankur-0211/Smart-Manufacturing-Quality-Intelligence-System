"""Stateless prediction and model metadata (roadmap 9.3.2; R2-P3 task 4). Thin routers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool

from app.api.deps import DatabaseDep, IntelligenceDep, RegistryDep
from app.api.errors import ApiError, ErrorCode, build_meta
from app.api.validation import validate_recipe
from app.contracts.explanation import GlobalExplanation, LocalExplanation
from app.db.errors import NotFoundError
from app.db.repositories import ModelVersionRepository
from app.schemas.envelope import Envelope
from app.schemas.prediction import (
    ActiveModelsOut,
    ModelVersionOut,
    PredictRequest,
    PredictResponse,
)
from app.services.inference_service import ExplanationUnavailableError, InferenceService

router = APIRouter(tags=["prediction"])

_REFERENCE_FIELDS = {
    "machine": "machine_id",
    "product": "product_id",
    "material lot": "material_lot_id",
}


def inference_service(database: DatabaseDep, intelligence: IntelligenceDep) -> InferenceService:
    return InferenceService(database, intelligence)


InferenceDep = Annotated[InferenceService, Depends(inference_service)]


@router.post(
    "/predict",
    response_model=Envelope[PredictResponse],
    summary="Evaluate a recipe end to end without a simulation run (persists the prediction)",
)
async def predict(
    request: Request, body: PredictRequest, service: InferenceDep, registry: RegistryDep
) -> Envelope[PredictResponse]:
    def validate(recipe: Mapping[str, float], context: Mapping[str, Any]) -> dict[str, float]:
        return validate_recipe(registry, recipe, context=context)

    try:
        inp = await run_in_threadpool(
            lambda: service.build_input(
                machine_id=body.machine_id,
                product_id=body.product_id,
                material_lot_id=body.material_lot_id,
                parameters=body.parameters.model_dump(),
                validate_parameters=validate,
            )
        )
    except NotFoundError as exc:
        raise ApiError(
            ErrorCode.REFERENCE_NOT_FOUND,
            str(exc),
            field=_REFERENCE_FIELDS.get(exc.entity),
            hint="Codes come from GET /machines, /products and /materials.",
        ) from exc
    # Intelligence errors map to the envelope through the IntelligenceError handler (9.1 table).
    result = await run_in_threadpool(
        lambda: service.predict(inp, include_explanation=body.include_explanation)
    )
    return Envelope(data=PredictResponse.model_validate(result), meta=build_meta(request))


@router.get(
    "/predict/{prediction_id}/explain",
    response_model=Envelope[LocalExplanation],
    summary="Local explanation of a stored prediction",
)
async def explain(
    request: Request, prediction_id: str, service: InferenceDep
) -> Envelope[LocalExplanation]:
    try:
        explanation = await run_in_threadpool(service.explanation, prediction_id)
    except NotFoundError as exc:
        raise ApiError(ErrorCode.PREDICTION_NOT_FOUND, str(exc), field="prediction_id") from exc
    except ExplanationUnavailableError as exc:
        raise ApiError(
            ErrorCode.MODEL_NOT_LOADED,
            str(exc),
            hint="Request /predict with include_explanation=true to store the explanation.",
        ) from exc
    return Envelope(data=explanation, meta=build_meta(request))


def _version_json(row: Any) -> dict[str, Any]:
    return {
        "version": f"{row.name}-{row.semver}",
        "name": row.name,
        "semver": row.semver,
        "algorithm": row.algorithm,
        "is_active": row.is_active,
        "trained_at": row.trained_at,
        "metrics": row.metrics or {},
        "feature_schema_hash": row.feature_schema_hash,
        "constraints_version": row.constraints_version,
        "threshold": row.threshold,
        "created_at": row.created_at,
    }


def _models(database: Any, *, active_only: bool) -> list[dict[str, Any]]:
    with database.session() as s:
        rows = ModelVersionRepository(s).all_versions()
        return [_version_json(r) for r in rows if r.is_active or not active_only]


@router.get(
    "/models/active", response_model=Envelope[ActiveModelsOut], summary="Models serving predictions"
)
async def active_models(
    request: Request, database: DatabaseDep, intelligence: IntelligenceDep
) -> Envelope[ActiveModelsOut]:
    info = intelligence.version_info()
    rows = await run_in_threadpool(lambda: _models(database, active_only=True))
    data = ActiveModelsOut(
        is_mock=info.is_mock,
        intelligence=info,
        models=[ModelVersionOut.model_validate(r) for r in rows],
    )
    return Envelope(data=data, meta=build_meta(request))


@router.get("/models", response_model=Envelope[list[ModelVersionOut]], summary="Model registry")
async def all_models(request: Request, database: DatabaseDep) -> Envelope[list[ModelVersionOut]]:
    rows = await run_in_threadpool(lambda: _models(database, active_only=False))
    return Envelope(
        data=[ModelVersionOut.model_validate(r) for r in rows], meta=build_meta(request)
    )


@router.get(
    "/models/active/global-explanation",
    response_model=Envelope[GlobalExplanation],
    summary="Global feature importance of the active model",
)
async def global_explanation(
    request: Request, intelligence: IntelligenceDep
) -> Envelope[GlobalExplanation]:
    data = await run_in_threadpool(intelligence.global_explanation)
    return Envelope(data=data, meta=build_meta(request))
