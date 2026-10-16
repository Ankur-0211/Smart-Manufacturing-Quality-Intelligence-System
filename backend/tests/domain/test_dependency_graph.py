"""Stage dependency graph (roadmap 8.4, 13.2). BOOTSTRAP by Role 2 (CCR-002)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.enums import INTELLIGENCE_STAGES, StageName
from app.contracts.recipe import RECIPE_FIELDS
from app.domain.constraint_loader import ConstraintRegistry
from app.domain.dependency_graph import StageDependencyGraph

S = StageName
DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return ConstraintRegistry.load(DOMAIN / "constraints.yaml")


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        (["moisture_pct"], list(INTELLIGENCE_STAGES)),
        (["melt_temp_c"], [S.PLASTICIZING, S.INJECTION, S.PACKING, S.COOLING]),
        (["clamp_force_ton"], [S.INJECTION, S.PACKING, S.COOLING]),
        # Roadmap 7.6 deviation: mold_temp_c is first read at PACKING, not COOLING.
        (["mold_temp_c"], [S.PACKING, S.COOLING]),
        (["cooling_time_s"], [S.COOLING]),
        # fill_time_s is read by INJECTION and COOLING: the earliest wins.
        (["fill_time_s"], [S.INJECTION, S.PACKING, S.COOLING]),
        (["cooling_time_s", "melt_temp_c"], [S.PLASTICIZING, S.INJECTION, S.PACKING, S.COOLING]),
        (["tonnage_ton"], []),  # fusion-only context
        ([], []),
    ],
)
def test_invalidated_stages(
    registry: ConstraintRegistry, changed: list[str], expected: list[StageName]
) -> None:
    assert registry.invalidated_stages(changed) == expected


def test_every_setpoint_invalidates_its_own_stage(registry: ConstraintRegistry) -> None:
    for name in RECIPE_FIELDS:
        stage = registry.parameter(name).stage
        assert stage is not None, name
        assert registry.invalidated_stages([name])[0] is stage


def test_stage_inputs_follow_the_registry(registry: ConstraintRegistry) -> None:
    assert "moisture_pct" in registry.stage_inputs(S.PLASTICIZING)
    assert registry.stage_inputs(S.PACKING) == [
        "hold_pressure_bar",
        "hold_time_s",
        "cushion_mm",
        "wall_thickness_mm",
        "mold_temp_c",
    ]
    with pytest.raises(ValueError):
        registry.stage_inputs(S.QUALITY_INSPECTION)


def test_graph_requires_all_five_stages() -> None:
    with pytest.raises(ValueError, match="COOLING"):
        StageDependencyGraph({s: [] for s in INTELLIGENCE_STAGES[:4]})
