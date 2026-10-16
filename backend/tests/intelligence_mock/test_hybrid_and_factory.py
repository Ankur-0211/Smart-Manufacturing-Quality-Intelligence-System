"""Hybrid routing and the intelligence factory (roadmap 9.1 factory table, UD-11)."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from app.api.deps import build_intelligence
from app.contracts.context import ProcessInput
from app.contracts.errors import CapabilityUnavailableError
from app.contracts.interface import QualityIntelligence
from app.core.config import IntelligenceBackendMode
from app.domain.constraint_loader import ConstraintRegistry
from app.intelligence_mock.hybrid import HybridQualityIntelligence
from app.intelligence_mock.mock import DEFAULT_REGISTRY, MockQualityIntelligence
from tests.conftest import make_settings

FIXTURE = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return ConstraintRegistry.load(DEFAULT_REGISTRY)


class PartialReal(MockQualityIntelligence):
    """TEST DOUBLE standing in for a real facade that only offers stage intelligence."""

    def capabilities(self) -> dict[str, bool]:
        return {"run_stage": True}

    def version_info(self) -> Any:
        info = super().version_info()
        return info.model_copy(update={"inference_backend": "real", "is_mock": False})


def test_hybrid_routes_per_capability(registry: ConstraintRegistry) -> None:
    real, mock = PartialReal(registry), MockQualityIntelligence(registry)
    hybrid = HybridQualityIntelligence(real, mock)
    assert isinstance(hybrid, QualityIntelligence)
    routing = hybrid.routing()
    assert routing["run_stage"] == "real" and routing["predict"] == "mock"
    info = hybrid.version_info()
    assert info.is_mock and info.inference_backend == "mock"  # anything mocked => labelled mock
    inp = ProcessInput.model_validate_json(FIXTURE.read_text("utf-8"))
    result = hybrid.evaluate(inp, include_explanation=True)
    assert result.prediction.is_mock  # predict came from the mock and says so
    assert result.prediction.explanation is not None


def test_factory_mock(registry: ConstraintRegistry) -> None:
    built = build_intelligence(make_settings(), registry)
    assert isinstance(built, MockQualityIntelligence)


def test_factory_hybrid_without_facade_is_all_mock(registry: ConstraintRegistry) -> None:
    built = build_intelligence(make_settings(intelligence_backend="hybrid"), registry)
    assert isinstance(built, MockQualityIntelligence)


def test_factory_real_refuses_to_start_without_facade(registry: ConstraintRegistry) -> None:
    with pytest.raises(CapabilityUnavailableError):
        build_intelligence(make_settings(intelligence_backend="real"), registry)


def _install_facade(monkeypatch: pytest.MonkeyPatch, facade_cls: type) -> None:
    pkg = types.ModuleType("app.intelligence")
    module = types.ModuleType("app.intelligence.facade")
    module.RealQualityIntelligence = facade_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "app.intelligence", pkg)
    monkeypatch.setitem(sys.modules, "app.intelligence.facade", module)


def test_factory_real_needs_p0_capabilities(
    registry: ConstraintRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Facade(PartialReal):
        @classmethod
        def from_settings(cls, settings: Any, reg: ConstraintRegistry) -> Facade:
            return cls(reg)

    _install_facade(monkeypatch, Facade)
    with pytest.raises(CapabilityUnavailableError, match="predict"):
        build_intelligence(make_settings(intelligence_backend="real"), registry)
    hybrid = build_intelligence(make_settings(intelligence_backend="hybrid"), registry)
    assert isinstance(hybrid, HybridQualityIntelligence)


def test_demo_profile_refuses_mock() -> None:
    with pytest.raises(ValueError, match="demo"):
        make_settings(env="demo", intelligence_backend=IntelligenceBackendMode.MOCK)
