"""Hybrid routing and the intelligence factory (roadmap 9.1 factory table, UD-11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.api.deps import build_intelligence
from app.contracts.context import ProcessInput
from app.contracts.errors import CapabilityUnavailableError
from app.contracts.interface import QualityIntelligence
from app.core.config import IntelligenceBackendMode
from app.domain.constraint_loader import ConstraintRegistry, load_constraint_registry
from app.intelligence.facade import RealQualityIntelligence
from app.intelligence_mock.hybrid import HybridQualityIntelligence
from app.intelligence_mock.mock import MockQualityIntelligence
from tests.conftest import make_settings

FIXTURE = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return load_constraint_registry()


class StagesOnlyReal(RealQualityIntelligence):
    """TEST DOUBLE: Role 1's facade restricted to stage intelligence."""

    def capabilities(self) -> dict[str, bool]:
        return {"run_stage": True}


def test_hybrid_routes_per_capability(registry: ConstraintRegistry) -> None:
    real, mock = StagesOnlyReal(registry=registry), MockQualityIntelligence(registry)
    hybrid = HybridQualityIntelligence(real, mock)
    assert isinstance(hybrid, QualityIntelligence)
    routing = hybrid.routing()
    assert routing["run_stage"] == "real" and routing["predict"] == "mock"
    assert hybrid.version_info().is_mock  # anything mocked => labelled mock
    inp = ProcessInput.model_validate_json(FIXTURE.read_text("utf-8"))
    result = hybrid.evaluate(inp, include_explanation=True)
    assert result.stage_results[0].module_version != "mock-0.0.0"  # stages came from Role 1
    assert result.prediction.is_mock  # predict came from the mock and says so
    assert result.prediction.explanation is not None


def test_hybrid_with_a_full_real_facade_is_real(registry: ConstraintRegistry) -> None:
    hybrid = HybridQualityIntelligence(
        RealQualityIntelligence(registry=registry), MockQualityIntelligence(registry)
    )
    assert set(hybrid.routing().values()) == {"real"}
    assert not hybrid.version_info().is_mock


def test_factory_modes(registry: ConstraintRegistry) -> None:
    assert isinstance(build_intelligence(make_settings(), registry), MockQualityIntelligence)
    hybrid = build_intelligence(make_settings(intelligence_backend="hybrid"), registry)
    assert isinstance(hybrid, HybridQualityIntelligence)
    real = build_intelligence(make_settings(intelligence_backend="real"), registry)
    assert isinstance(real, RealQualityIntelligence)
    assert real.registry is registry  # Role 1's facade shares the app's registry


def test_factory_real_needs_p0_capabilities(
    registry: ConstraintRegistry, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_recommend(self: Any) -> dict[str, bool]:
        return {"run_stage": True, "predict": True, "explain": True, "recommend": False}

    monkeypatch.setattr(RealQualityIntelligence, "capabilities", no_recommend)
    with pytest.raises(CapabilityUnavailableError, match="recommend"):
        build_intelligence(make_settings(intelligence_backend="real"), registry)


def test_demo_profile_refuses_mock() -> None:
    with pytest.raises(ValueError, match="demo"):
        make_settings(env="demo", intelligence_backend=IntelligenceBackendMode.MOCK)
