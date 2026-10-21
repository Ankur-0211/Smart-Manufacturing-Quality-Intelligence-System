"""FastAPI dependencies and the intelligence factory (roadmap 9.1).

``build_intelligence`` is the single wiring point allowed to construct the real facade (rule B2,
``tests/test_import_boundaries.py``). Everything else reaches the intelligence through
``QualityIntelligence``.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, Request

from app.api.errors import ApiError, ErrorCode
from app.contracts.errors import CapabilityUnavailableError
from app.contracts.interface import QualityIntelligence
from app.core.config import Environment, IntelligenceBackendMode, Settings
from app.core.logging import get_logger
from app.db.session import Database
from app.domain.constraint_loader import ConstraintRegistry, load_constraint_registry
from app.intelligence_mock.hybrid import HybridQualityIntelligence
from app.intelligence_mock.mock import MockQualityIntelligence

log = get_logger("app.intelligence")

# Capabilities `real` mode must provide at startup (roadmap 9.1 factory table).
P0_CAPABILITIES: tuple[str, ...] = ("run_stage", "predict", "explain", "recommend")


def load_registry(settings: Settings) -> ConstraintRegistry:
    """Role 1's registry from ``SMQI_CONSTRAINTS_PATH``; raises ``RegistryInvalidError``."""
    return load_constraint_registry(settings.constraints_path)


def _load_real(registry: ConstraintRegistry) -> QualityIntelligence | None:
    """Role 1's facade (constructed as documented in aboutrole1.md), or None if absent."""
    try:
        from app.intelligence.facade import RealQualityIntelligence
    except ModuleNotFoundError:
        return None
    real: QualityIntelligence = RealQualityIntelligence(registry=registry)
    return real


def build_intelligence(settings: Settings, registry: ConstraintRegistry) -> QualityIntelligence:
    """Choose the implementation per ``SMQI_INTELLIGENCE_BACKEND`` (9.1 factory table)."""
    mode = settings.intelligence_backend
    if mode is not IntelligenceBackendMode.REAL and settings.env is Environment.DEMO:
        # Settings already refuses this; repeated here so the factory is safe on its own.
        raise CapabilityUnavailableError("SMQI_ENV=demo requires SMQI_INTELLIGENCE_BACKEND=real")
    if mode is IntelligenceBackendMode.MOCK:
        return MockQualityIntelligence(registry)

    real = _load_real(registry)
    if mode is IntelligenceBackendMode.HYBRID:
        mock = MockQualityIntelligence(registry)
        if real is None:
            log.warning(
                "hybrid_without_real_facade", detail="every capability is served by the mock"
            )
            return mock
        return HybridQualityIntelligence(real, mock)

    if real is None:
        raise CapabilityUnavailableError(
            "SMQI_INTELLIGENCE_BACKEND=real but app.intelligence.facade is not available yet",
            hint="Use mock or hybrid until Role 1 delivers the facade (R1-P5).",
        )
    caps = real.capabilities()
    missing = [c for c in P0_CAPABILITIES if not caps.get(c)]
    if missing:
        raise CapabilityUnavailableError(
            f"real intelligence lacks P0 capabilities: {', '.join(missing)}", details=missing
        )
    return real


def app_settings(request: Request) -> Settings:
    """The Settings instance the app was created with (see ``create_app``)."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(app_settings)]


def app_database(request: Request) -> Database:
    """The Database (engine + session factory) owned by this app instance."""
    database: Database = request.app.state.db
    return database


DatabaseDep = Annotated[Database, Depends(app_database)]


def get_intelligence(request: Request) -> QualityIntelligence:
    """The process-wide intelligence chosen at startup."""
    intelligence: QualityIntelligence = request.app.state.intelligence
    return intelligence


IntelligenceDep = Annotated[QualityIntelligence, Depends(get_intelligence)]


def get_registry(request: Request) -> ConstraintRegistry:
    registry: ConstraintRegistry = request.app.state.registry
    return registry


RegistryDep = Annotated[ConstraintRegistry, Depends(get_registry)]


def require_api_key(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Optional static API key (Plan 16.6): enforced only when ``SMQI_API_KEY`` is set."""
    if settings.api_key is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise ApiError(
            ErrorCode.UNAUTHORIZED,
            "Missing or invalid X-API-Key header",
            hint="Send the X-API-Key header configured for this deployment.",
        )
