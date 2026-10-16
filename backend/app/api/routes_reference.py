"""Reference endpoints (roadmap 9.3.2). R2-P1 task 9 adds ``/constraints``; ``/machines``,
``/products`` and ``/materials`` follow in R2-P3.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, Request, Response

from app.api.deps import RegistryDep
from app.api.errors import build_meta
from app.schemas.constraints import ConstraintsOut
from app.schemas.envelope import Envelope

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
