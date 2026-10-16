"""ConstraintRegistry loader (roadmap 8.4, R1-P1 task 10). BOOTSTRAP by Role 2 (CCR-002)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.contracts.context import ProcessInput
from app.contracts.enums import ConstraintSeverity, ParameterKind, StageName
from app.contracts.errors import RegistryInvalidError, UnknownParameterError
from app.contracts.recipe import RECIPE_FIELDS
from app.domain.constraint_loader import ConstraintRegistry

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DOMAIN / "constraints.yaml").read_text("utf-8"))
    return data


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return ConstraintRegistry.load(DOMAIN / "constraints.yaml")


def _flat(fixture: str) -> dict[str, Any]:
    inp = ProcessInput.model_validate_json((FIXTURES / f"{fixture}.json").read_text("utf-8"))
    return inp.flat()


def test_loads_shipped_registry(registry: ConstraintRegistry) -> None:
    assert registry.version == "constraints-0.1.0"
    assert len(registry.content_hash) == 64
    setpoints = [p.name for p in registry.parameters(ParameterKind.SETPOINT)]
    assert setpoints == list(RECIPE_FIELDS)
    assert registry.parameter("melt_temp_c").stage is StageName.PLASTICIZING
    assert registry.resin_grade("PP-H").degradation_ceiling_c == 285


def test_content_hash_is_stable_and_content_sensitive(raw: dict[str, Any]) -> None:
    a = ConstraintRegistry.from_mapping(copy.deepcopy(raw))
    b = ConstraintRegistry.from_mapping(copy.deepcopy(raw))
    assert a.content_hash == b.content_hash
    changed = copy.deepcopy(raw)
    changed["parameters"]["melt_temp_c"]["max"] = 296
    assert ConstraintRegistry.from_mapping(changed).content_hash != a.content_hash


def test_unknown_lookups_raise(registry: ConstraintRegistry) -> None:
    with pytest.raises(UnknownParameterError):
        registry.parameter("warp_factor")
    with pytest.raises(UnknownParameterError):
        registry.resin_grade("ABS")
    with pytest.raises(UnknownParameterError):
        registry.invalidated_stages(["warp_factor"])


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("recipe_nominal", set()),
        ("recipe_short_cooling", set()),  # HC-004 needs the derived minimum from S5
        ("recipe_clamp_insufficient", set()),  # HC-002 needs required clamp force from S3
        ("recipe_melt_ceiling_breach", {"HC-001"}),
        ("recipe_high_moisture", {"HC-006"}),
    ],
)
def test_fixture_rule_outcomes(
    registry: ConstraintRegistry, fixture: str, expected: set[str]
) -> None:
    values = _flat(fixture)
    assert registry.check_box(values) == []
    assert registry.check_couplings(values) == []
    assert {b.rule_id for b in registry.check_hard_constraints(values)} == expected


def test_derived_rules_fire_when_the_stage_supplies_the_value(registry: ConstraintRegistry) -> None:
    values = _flat("recipe_clamp_insufficient")
    required = values["clamp_force_ton"] + 25
    (breach,) = registry.check_hard_constraints(
        values, {"required_clamp_force_ton": required}, stage=StageName.INJECTION
    )
    assert breach.rule_id == "HC-002"
    assert breach.severity is ConstraintSeverity.CRITICAL
    assert registry.hard_constraint("HC-002").blocks_stage
    assert breach.limit == required
    assert breach.constraints_version == registry.version


def test_hard_constraint_payload(registry: ConstraintRegistry) -> None:
    (breach,) = registry.check_hard_constraints(_flat("recipe_high_moisture"))
    assert breach.parameters == ["moisture_pct"]
    assert breach.limit == pytest.approx(0.20)  # spec 0.10 x critical factor 2.0
    assert breach.hint


def test_stage_filter(registry: ConstraintRegistry) -> None:
    values = _flat("recipe_melt_ceiling_breach")
    assert registry.check_hard_constraints(values, stage=StageName.INJECTION) == []
    assert registry.check_hard_constraints(values, stage=StageName.PLASTICIZING)


def test_check_box(registry: ConstraintRegistry) -> None:
    breaches = registry.check_box(
        {
            "melt_temp_c": 300,
            "cavity_count": 2,
            "machine_age_days": 1.5,
            "screw_rpm": "fast",
            "machine_id": "MC-03",  # identity: ignored
            "mold_temp_c": None,  # absent: ignored
        }
    )
    by_param = {b.parameters[0]: b for b in breaches}
    assert set(by_param) == {"melt_temp_c", "cavity_count", "machine_age_days", "screw_rpm"}
    assert by_param["melt_temp_c"].value == 300
    assert by_param["melt_temp_c"].limit == 295
    assert all(b.severity is ConstraintSeverity.CRITICAL for b in breaches)


def test_check_couplings(registry: ConstraintRegistry) -> None:
    values = {
        "hold_pressure_bar": 950,
        "inj_pressure_bar": 900,
        "melt_temp_c": 150,
        "mold_temp_c": 40,
    }
    breaches = {b.rule_id: b for b in registry.check_couplings(values)}
    assert set(breaches) == {"CPL-001", "CPL-002"}
    assert breaches["CPL-002"].limit == 160
    assert registry.check_couplings({"hold_pressure_bar": 950}) == []  # missing operand


def test_public_dict_is_json_and_a_copy(registry: ConstraintRegistry) -> None:
    public = registry.to_public_dict()
    assert public["version"] == registry.version
    assert public["content_hash"] == registry.content_hash
    names = [p["name"] for p in public["parameters"]]
    assert names[: len(RECIPE_FIELDS)] == list(RECIPE_FIELDS)
    json.dumps(public)
    public["parameters"].clear()
    assert registry.to_public_dict()["parameters"]


def _broken(raw: dict[str, Any], mutate: Any) -> dict[str, Any]:
    doc = copy.deepcopy(raw)
    mutate(doc)
    return doc


@pytest.mark.parametrize(
    "mutate",
    [
        pytest.param(lambda d: d.pop("risk_bands"), id="missing-block"),
        pytest.param(lambda d: d.update(registry_version="1.0"), id="bad-version"),
        pytest.param(lambda d: d["parameters"].pop("cushion_mm"), id="missing-setpoint"),
        pytest.param(
            lambda d: d["parameters"].update(extra_knob=dict(d["parameters"]["cushion_mm"])),
            id="unexpected-setpoint",
        ),
        pytest.param(
            lambda d: d["parameters"]["melt_temp_c"].update(nominal=400), id="nominal-out"
        ),
        pytest.param(lambda d: d["parameters"]["melt_temp_c"].update(unit="kelvin"), id="bad-unit"),
        pytest.param(
            lambda d: d["parameters"]["mold_temp_c"].update(stage="COOLING"), id="stage-mismatch"
        ),
        pytest.param(lambda d: d["stage_inputs"]["PACKING"].append("ghost"), id="unknown-input"),
        pytest.param(lambda d: d["resin_grades"].pop("PP-C"), id="grade-mismatch"),
        pytest.param(
            lambda d: d["coupling_rules"][0].update(left="ghost"), id="coupling-unknown-param"
        ),
        pytest.param(
            lambda d: d["hard_constraints"][0].update(grade_field="ghost_c"),
            id="unknown-grade-field",
        ),
        pytest.param(
            lambda d: d["hard_constraints"][2].update(blocks_stage=True), id="warning-blocks"
        ),
        pytest.param(
            lambda d: d["risk_bands"]["stage_health"].update(LOW=0.95), id="bands-not-monotone"
        ),
        pytest.param(
            lambda d: d["stage_checks"]["PACKING"][0].update(weight=0.9), id="weights-over-one"
        ),
        pytest.param(
            lambda d: d["parameters"]["mfi"].update(
                actionable=True, change_cost=0.1, max_step_change=1
            ),
            id="lot-attribute-actionable",
        ),
    ],
)
def test_invalid_registry_fails_fast(raw: dict[str, Any], mutate: Any) -> None:
    with pytest.raises(RegistryInvalidError) as exc:
        ConstraintRegistry.from_mapping(_broken(raw, mutate))
    assert exc.value.code == "REGISTRY_INVALID"


def test_unreadable_file_fails_fast(tmp_path: Path) -> None:
    bad = tmp_path / "constraints.yaml"
    bad.write_text("parameters: [unclosed", encoding="utf-8")
    with pytest.raises(RegistryInvalidError):
        ConstraintRegistry.load(bad)
    with pytest.raises(RegistryInvalidError):
        ConstraintRegistry.load(tmp_path / "missing.yaml")
