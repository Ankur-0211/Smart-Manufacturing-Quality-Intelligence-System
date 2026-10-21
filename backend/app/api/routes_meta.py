"""Meta endpoints. R2-P1 provides ``/health``; ``/constraints`` (R2-P1 task 9) and ``/models``
(R2-P3) follow.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from app.api.deps import DatabaseDep, IntelligenceDep, RegistryDep, SettingsDep
from app.api.errors import build_meta
from app.contracts.interface import IntelligenceVersionInfo
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
    intelligence: IntelligenceVersionInfo
    components: list[ComponentStatus]


@router.get("/health", response_model=Envelope[HealthData], summary="Liveness and readiness")
def health(
    request: Request,
    settings: SettingsDep,
    database: DatabaseDep,
    intelligence: IntelligenceDep,
    registry: RegistryDep,
) -> Envelope[HealthData]:
    # Components are reported honestly: anything not built yet is "available": false.
    db_status = database.status()
    info = intelligence.version_info()
    components = [
        ComponentStatus(name="api", available=True, detail="FastAPI application running"),
        ComponentStatus(name="database", available=db_status.migrated, detail=db_status.detail),
        ComponentStatus(
            name="intelligence",
            available=True,
            detail=(
                "MOCK intelligence: outputs are placeholders, not model predictions"
                if info.is_mock
                else f"Real intelligence ({info.model_version})"
            ),
        ),
        ComponentStatus(
            name="constraint_registry",
            available=True,
            detail=f"{registry.version} (sha256 {registry.content_hash[:12]})",
        ),
    ]
    status: Literal["ok", "degraded"] = "ok" if all(c.available for c in components) else "degraded"
    data = HealthData(
        status=status,
        env=settings.env.value,
        intelligence_backend=settings.intelligence_backend.value,
        db=db_status.migrated,
        model_loaded=not info.is_mock,
        intelligence=info,
        components=components,
    )
    return Envelope(data=data, meta=build_meta(request))
