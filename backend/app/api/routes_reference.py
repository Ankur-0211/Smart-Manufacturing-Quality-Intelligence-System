"""Reference endpoints (roadmap 9.3.2): ``/constraints`` (R2-P1 task 9) and the machines,
products and material lots a run is built from (R2-P3). Thin: logic lives in ReferenceService.
"""

from __future__ import annotations

import re
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.concurrency import run_in_threadpool

from app.api.deps import DatabaseDep, RegistryDep
from app.api.errors import ApiError, ErrorCode, build_meta
from app.api.validation import validate_lot_attributes
from app.db.errors import DuplicateError
from app.schemas.constraints import ConstraintsOut
from app.schemas.envelope import Envelope
from app.schemas.reference import (
    CODE_PATTERN,
    MachineOut,
    MaterialLotCreate,
    MaterialLotOut,
    ProductOut,
)
from app.services.reference_service import ReferenceService

router = APIRouter(tags=["reference"])


@router.get(
    "/constraints",
    response_model=Envelope[ConstraintsOut],
    summary="Constraint registry: windows, units, steps, rules and bands",
    responses={304: {"description": "Unchanged since the ETag sent in If-None-Match"}},
)
def get_constraints(
    request: Request,
    response: Response,
    registry: RegistryDep,
    if_none_match: str | None = Header(default=None),
) -> Envelope[ConstraintsOut] | Response:
    etag = f'"{registry.content_hash}"'
    if if_none_match is not None and etag in {t.strip() for t in if_none_match.split(",")}:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "no-cache"  # revalidate; the registry changes per deploy
    data = ConstraintsOut.model_validate(registry.to_public_dict())
    return Envelope(data=data, meta=build_meta(request))


def reference_service(database: DatabaseDep) -> ReferenceService:
    return ReferenceService(database)


ReferenceDep = Annotated[ReferenceService, Depends(reference_service)]


@router.get("/machines", response_model=Envelope[list[MachineOut]], summary="Active machines")
async def list_machines(request: Request, service: ReferenceDep) -> Envelope[list[MachineOut]]:
    rows = await run_in_threadpool(service.machines)
    return Envelope(data=[MachineOut.model_validate(r) for r in rows], meta=build_meta(request))


@router.get("/products", response_model=Envelope[list[ProductOut]], summary="Active products")
async def list_products(request: Request, service: ReferenceDep) -> Envelope[list[ProductOut]]:
    rows = await run_in_threadpool(service.products)
    return Envelope(data=[ProductOut.model_validate(r) for r in rows], meta=build_meta(request))


@router.get("/materials", response_model=Envelope[list[MaterialLotOut]], summary="Material lots")
async def list_materials(request: Request, service: ReferenceDep) -> Envelope[list[MaterialLotOut]]:
    rows = await run_in_threadpool(service.materials)
    return Envelope(data=[MaterialLotOut.model_validate(r) for r in rows], meta=build_meta(request))


@router.post(
    "/materials",
    status_code=201,
    response_model=Envelope[MaterialLotOut],
    summary="Create a material lot (attributes validated against the registry)",
)
async def create_material(
    request: Request, body: MaterialLotCreate, service: ReferenceDep, registry: RegistryDep
) -> Envelope[MaterialLotOut]:
    if not re.fullmatch(CODE_PATTERN, body.material_lot_id):
        raise ApiError(
            ErrorCode.VALIDATION_ERROR,
            "material_lot_id must be 1-32 letters, digits, '.', '_' or '-'",
            field="material_lot_id",
        )
    try:
        row = await run_in_threadpool(
            service.create_material,
            body.model_dump(),
            validate_attributes=partial(validate_lot_attributes, registry),
        )
    except DuplicateError as exc:
        raise ApiError(
            ErrorCode.VALIDATION_ERROR,
            str(exc),
            status_code=409,
            field="material_lot_id",
            hint="Lot codes are unique; choose another code.",
        ) from exc
    return Envelope(data=MaterialLotOut.model_validate(row), meta=build_meta(request))
