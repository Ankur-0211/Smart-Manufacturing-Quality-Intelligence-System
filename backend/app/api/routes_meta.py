"""Meta endpoints. R2-P1 provides ``/health``; ``/constraints`` and ``/models`` follow
once the Role 1 registry loader and contracts are integrated (R2-P1 task 9, R2-P3).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import SettingsDep
from app.api.errors import build_meta
from app.schemas.envelope import Envelope

router = APIRouter(tags=["meta"])


class ComponentStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    available: bool
    detail: str


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "degraded"]
    env: str
    intelligence_backend: str
    db: bool
    model_loaded: bool
    # IntelligenceVersionInfo (roadmap 9.1) once contracts exist; null until then.
    intelligence: dict[str, object] | None = None
    components: list[ComponentStatus]


@router.get("/health", response_model=Envelope[HealthData], summary="Liveness and readiness")
def health(request: Request, settings: SettingsDep) -> Envelope[HealthData]:
    # Components are reported honestly: anything not built yet is "available": false.
    components = [
        ComponentStatus(name="api", available=True, detail="FastAPI application running"),
        ComponentStatus(name="database", available=False, detail="Not configured yet (R2-P2)"),
        ComponentStatus(
            name="intelligence",
            available=False,
            detail="Awaiting app.contracts v0.1.0 from Role 1 (R2-P1 tasks 8-10)",
        ),
        ComponentStatus(
            name="constraint_registry",
            available=settings.constraints_path.is_file(),
            detail=(
                "Registry file present (loader integration pending)"
                if settings.constraints_path.is_file()
                else "constraints.yaml not delivered yet (R1-P1)"
            ),
        ),
    ]
    status: Literal["ok", "degraded"] = "ok" if all(c.available for c in components) else "degraded"
    data = HealthData(
        status=status,
        env=settings.env.value,
        intelligence_backend=settings.intelligence_backend.value,
        db=False,
        model_loaded=False,
        intelligence=None,
        components=components,
    )
    return Envelope(data=data, meta=build_meta(request))
