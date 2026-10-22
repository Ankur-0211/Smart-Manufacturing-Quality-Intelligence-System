"""What Role 2 relies on from Role 1's constraint registry (roadmap 8.4, 8.5).

These are integration expectations, not tests of Role 1's rules: if Role 1 changes one of them,
Role 2's validation, /constraints payload, simulation display or demo data must change too.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.enums import INTELLIGENCE_STAGES
from app.contracts.recipe import RECIPE_FIELDS
from app.db.seed import load_fleet
from app.domain.constraint_loader import ConstraintRegistry, load_constraint_registry

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return load_constraint_registry()


def test_every_setpoint_has_a_window(registry: ConstraintRegistry) -> None:
    """Tier-1 validation and the UI sliders are generated from these fields (rule B6)."""
    setpoints = [n for n, s in registry.parameters.items() if s.get("kind") == "setpoint"]
    assert setpoints == list(RECIPE_FIELDS)
    for name in RECIPE_FIELDS:
        spec = registry.get_parameter(name)
        assert spec is not None
        assert spec["min"] <= spec["nominal"] <= spec["max"], name
        assert spec["step"] > 0 and spec["display_name"], name
        assert registry.check_box(name, spec["nominal"])[0], name


def test_every_setpoint_belongs_to_a_stage(registry: ConstraintRegistry) -> None:
    """``stage.started`` shows ``stage_inputs``; every setpoint appears under exactly one stage."""
    seen = [n for stage in INTELLIGENCE_STAGES for n in registry.stage_inputs(stage)]
    assert sorted(seen) == sorted(RECIPE_FIELDS)


def test_public_payload_has_the_served_blocks(registry: ConstraintRegistry) -> None:
    public = registry.to_public_dict()
    assert {
        "registry_version",
        "content_hash",
        "parameters",
        "coupling_rules",
        "hard_constraints",
        "resin_grades",
        "risk_bands",
    } <= set(public)
    assert public["registry_version"] == registry.version
    assert {"stage_health", "p_fail"} <= set(public["risk_bands"])


def test_fleet_seeds_and_covers_the_demo(registry: ConstraintRegistry) -> None:
    """The DB seed reads Role 1's fleet; the demo needs a passing and a blocking lot."""
    fleet = load_fleet(DOMAIN / "fleet.yaml")
    assert {lot.resin_grade for lot in fleet.material_lots} <= set(registry.resin_grades)
    grade = registry.get_resin_grade
    wet = [
        lot.material_lot_id
        for lot in fleet.material_lots
        if lot.moisture_pct
        > grade(lot.resin_grade)["moisture_spec_max_pct"]
        * grade(lot.resin_grade)["moisture_critical_factor"]
    ]
    assert wet, "the demo needs a lot that trips HC-006"
    assert len(wet) < len(fleet.material_lots)
