"""Data-level checks of the CCR-002 bootstrap files (constraints.yaml, remedies.yaml, fleet.yaml,
contract fixtures). They need no loader and no Role 1 contract code, so they run today.

When ``constraint_loader.py`` lands, the loader tests (roadmap R1-P1 task 10) take over rule
evaluation; these checks stay as a guard on the raw files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.db.seed import FleetFile
from app.db.vocab import RECIPE_FIELDS, STAGE_NAMES

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"

# Indicator keys per stage (roadmap §7.10) that stage_checks / remedies may reference.
STAGE_INDICATORS = {
    "MATERIAL_CONDITIONING": {
        "dryness_margin",
        "mfi_z",
        "moisture_z",
        "moisture_risk",
        "regrind_margin",
        "viscosity_class",
        "moisture_flag",
    },
    "PLASTICIZING": {
        "thermal_exposure",
        "degradation_exposure",
        "shear_heat_offset_c",
        "effective_melt_temp_c",
        "temp_profile_slope",
        "profile_monotonic",
        "splay_risk",
        "melt_consistency",
    },
    "INJECTION": {
        "fill_index",
        "shear_rate_proxy",
        "pressure_headroom",
        "cavity_pressure_estimate_bar",
        "required_clamp_force_ton",
        "short_shot_risk",
        "flash_risk",
        "fill_completion_proxy",
    },
    "PACKING": {
        "packing_integral",
        "gate_freeze_estimate_s",
        "hold_vs_freeze_ratio",
        "sink_void_risk",
        "over_pack_risk",
        "cushion_ok",
        "residual_stress_proxy",
    },
    "COOLING": {
        "required_cooling_estimate_s",
        "cooling_adequacy",
        "warp_risk",
        "ejection_risk",
        "dimensional_stability_index",
        "cycle_consistency",
        "cycle_balance",
    },
}


def _yaml(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DOMAIN / name).read_text(encoding="utf-8"))
    return data


@pytest.fixture(scope="module")
def reg() -> dict[str, Any]:
    return _yaml("constraints.yaml")


@pytest.fixture(scope="module")
def params(reg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = reg["parameters"]
    return out


def _fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        (FIXTURES / f"recipe_{name}.json").read_text(encoding="utf-8")
    )
    return data


def _flat(doc: dict[str, Any]) -> dict[str, Any]:
    ctx = doc["context"]
    return {**ctx["machine"], **ctx["product"], **ctx["material_lot"], **doc["recipe"]}


# ---------------------------------------------------------------- registry structure


def test_registry_header(reg: dict[str, Any]) -> None:
    assert reg["registry_version"].startswith("constraints-")
    for section in (
        "resin_grades",
        "stage_inputs",
        "parameters",
        "coupling_rules",
        "hard_constraints",
        "stage_checks",
        "risk_bands",
        "recommendation",
        "submodels",
    ):
        assert section in reg, section


def test_setpoints_are_the_canonical_recipe_in_order(params: dict[str, dict[str, Any]]) -> None:
    setpoints = [k for k, v in params.items() if v["kind"] == "setpoint"]
    assert tuple(setpoints) == RECIPE_FIELDS


def test_every_parameter_has_required_metadata(
    reg: dict[str, Any], params: dict[str, dict[str, Any]]
) -> None:
    units = set(reg["units_allowed"])
    for name, p in params.items():
        assert p["kind"] in {
            "setpoint",
            "lot_attribute",
            "product_context",
            "machine_context",
        }, name
        assert "provenance" in p and "citation" in p and "display_name" in p, name
        assert p["unit"] is None or p["unit"] in units, name
        if "allowed_values" in p:
            assert p["nominal"] in p["allowed_values"], name
            continue
        assert p["min"] <= p["nominal"] <= p["max"], name
        assert p["min"] < p["max"], name
        assert p["step"] > 0, name
        if p.get("max_step_change") is not None:
            assert 0 < p["max_step_change"] <= p["max"] - p["min"], name
        if p["kind"] == "setpoint" and p["actionable"]:
            assert 0 <= p["change_cost"] <= 1 and p["max_step_change"] is not None, name
        if p["kind"] != "setpoint":
            assert p["actionable"] is False, (
                f"{name}: context/lot fields are never knobs (Plan 14.7)"
            )


def test_parameter_stage_is_earliest_consuming_stage(
    reg: dict[str, Any], params: dict[str, dict[str, Any]]
) -> None:
    slices: dict[str, list[str]] = reg["stage_inputs"]
    assert tuple(slices) == STAGE_NAMES
    for stage, fields in slices.items():
        unknown = set(fields) - set(params)
        assert not unknown, f"{stage} slice references unknown fields {unknown}"
    for name, p in params.items():
        earliest = next((s for s in STAGE_NAMES if name in slices[s]), None)
        assert p["stage"] == earliest, f"{name}: stage {p['stage']} != earliest consumer {earliest}"


def test_rules_reference_known_fields(
    reg: dict[str, Any], params: dict[str, dict[str, Any]]
) -> None:
    grade_fields = set().union(*(g.keys() for g in reg["resin_grades"].values()))
    for rule in reg["coupling_rules"]:
        assert {rule["left"], rule["right"]} <= set(params), rule["id"]
        assert rule["severity"] == "CRITICAL"
    for rule in reg["hard_constraints"]:
        assert rule["param"] in params, rule["id"]
        assert rule["stage"] in STAGE_NAMES, rule["id"]
        for key in ("grade_field", "factor_field"):
            if key in rule:
                assert rule[key] in grade_fields, rule["id"]
        if "other" in rule:
            assert rule["other"] in params, rule["id"]
        assert rule["blocks_stage"] == (rule["severity_in_simulation"] == "CRITICAL"), rule["id"]
    assert [r["id"] for r in reg["hard_constraints"]] == [f"HC-00{i}" for i in range(1, 7)]


def test_stage_checks_reference_inputs_or_indicators(reg: dict[str, Any]) -> None:
    for stage, checks in reg["stage_checks"].items():
        allowed = set(reg["stage_inputs"][stage]) | STAGE_INDICATORS[stage]
        for c in checks:
            assert c["target"] in allowed, f"{stage}/{c['check_id']} -> {c['target']}"
            assert c["type"] in {"range", "zscore", "indicator"}
        assert 0 < sum(c["weight"] for c in checks) <= 1.0, stage


def test_risk_bands_are_monotone(reg: dict[str, Any]) -> None:
    h = reg["risk_bands"]["stage_health"]
    assert h["NORMAL"] > h["LOW"] > h["MEDIUM"] > h["HIGH"] > 0
    p = reg["risk_bands"]["p_fail"]
    assert 0 < p["LOW"] < p["MEDIUM"] < p["HIGH"] < p["CRITICAL"] < 1


def test_resin_grades(reg: dict[str, Any], params: dict[str, dict[str, Any]]) -> None:
    assert set(reg["resin_grades"]) == set(params["resin_grade"]["allowed_values"])
    melt = params["melt_temp_c"]
    for name, g in reg["resin_grades"].items():
        lo, hi = g["melt_window_c"]
        assert melt["min"] <= lo < hi <= g["degradation_ceiling_c"] <= melt["max"], name


def test_remedies_reference_known_parameters_and_indicators(
    reg: dict[str, Any], params: dict[str, dict[str, Any]]
) -> None:
    remedies = _yaml("remedies.yaml")
    hard_ids = {r["id"] for r in reg["hard_constraints"]}
    for rule in remedies["rules"]:
        when = rule["when"]
        if "breach" in when:
            assert when["breach"] in hard_ids, rule["id"]
        else:
            assert when["indicator"] in STAGE_INDICATORS[when["stage"]], rule["id"]
        for action in rule["actions"]:
            p = params[action["parameter"]]
            assert p["kind"] == "setpoint" and p["actionable"], (
                f"{rule['id']}: {action['parameter']} is not a knob"
            )
            assert action["direction"] in {"increase", "decrease"}


# ---------------------------------------------------------------- fleet


def test_fleet_validates_with_seed_schema(
    reg: dict[str, Any], params: dict[str, dict[str, Any]]
) -> None:
    fleet = FleetFile.model_validate(_yaml("fleet.yaml"))
    assert {"MC-01", "MC-02", "MC-03", "MC-04"} <= {m.machine_id for m in fleet.machines}
    assert "PP-JBOX-42" in {p.product_id for p in fleet.products}
    assert "A-771" in {lot.material_lot_id for lot in fleet.material_lots}
    for lot in fleet.material_lots:
        assert lot.resin_grade in reg["resin_grades"], lot.material_lot_id
        for field in ("mfi", "moisture_pct", "regrind_pct", "colourant_pct"):
            v = getattr(lot, field)
            assert params[field]["min"] <= v <= params[field]["max"], (lot.material_lot_id, field)
    for m in fleet.machines:
        for field in ("tonnage_ton", "max_inj_pressure_bar", "max_clamp_force_ton"):
            assert params[field]["min"] <= getattr(m, field) <= params[field]["max"], (
                m.machine_id,
                field,
            )


# ---------------------------------------------------------------- fixtures

FIXTURE_NAMES = [
    "nominal",
    "melt_ceiling_breach",
    "short_cooling",
    "clamp_insufficient",
    "high_moisture",
]


def _static_breaches(reg: dict[str, Any], flat: dict[str, Any]) -> set[str]:
    """Rules that can be evaluated from raw inputs alone (min_derived needs stage computations)."""
    grade = reg["resin_grades"][flat["resin_grade"]]
    out: set[str] = set()
    for r in reg["coupling_rules"]:
        left, right = flat[r["left"]], flat[r["right"]]
        ok = left <= right if r["kind"] == "le" else left >= right + r["offset"]
        if not ok:
            out.add(r["id"])
    for r in reg["hard_constraints"]:
        v = flat[r["param"]]
        kind = r["kind"]
        if kind == "max_from_grade":
            ok = v <= grade[r["grade_field"]]
        elif kind == "max_from_grade_factor":
            ok = v <= grade[r["grade_field"]] * grade[r["factor_field"]]
        elif kind == "max_ratio":
            ok = v <= r["factor"] * flat[r["other"]]
        elif kind == "range":
            ok = r["min"] <= v <= r["max"]
        else:
            continue
        if not ok:
            out.add(r["id"])
    return out


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_shape_and_boxes(name: str, params: dict[str, dict[str, Any]]) -> None:
    doc = _fixture(name)
    assert set(doc) == {"context", "recipe"}
    assert set(doc["context"]) == {"machine", "product", "material_lot"}
    assert tuple(doc["recipe"]) == RECIPE_FIELDS
    flat = _flat(doc)
    for field, p in params.items():
        assert field in flat, f"{name}: missing {field}"
        if "allowed_values" in p:
            assert flat[field] in p["allowed_values"], (name, field)
        else:
            assert p["min"] <= flat[field] <= p["max"], f"{name}: {field}={flat[field]} outside box"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("nominal", set()),
        ("melt_ceiling_breach", {"HC-001"}),
        ("short_cooling", set()),  # HC-004 needs the stage-derived minimum (Role 1)
        ("clamp_insufficient", set()),  # HC-002 needs the stage-derived clamp requirement (Role 1)
        ("high_moisture", {"HC-006"}),
    ],
)
def test_fixture_static_breaches(name: str, expected: set[str], reg: dict[str, Any]) -> None:
    assert _static_breaches(reg, _flat(_fixture(name))) == expected


@pytest.mark.parametrize(
    ("name", "changed"),
    [
        ("melt_ceiling_breach", {"melt_temp_c", "barrel_temp_front_c", "nozzle_temp_c"}),
        ("short_cooling", {"cooling_time_s", "cycle_time_s"}),
        ("clamp_insufficient", {"clamp_force_ton"}),
        ("high_moisture", set()),  # differs only in the material lot
    ],
)
def test_fixture_differs_from_nominal_only_where_intended(name: str, changed: set[str]) -> None:
    base, doc = _fixture("nominal"), _fixture(name)
    diff = {k for k in RECIPE_FIELDS if doc["recipe"][k] != base["recipe"][k]}
    assert diff == changed
    if name == "short_cooling":  # UD-09: cycle time follows the cooling-time delta
        d_cool = doc["recipe"]["cooling_time_s"] - base["recipe"]["cooling_time_s"]
        d_cycle = doc["recipe"]["cycle_time_s"] - base["recipe"]["cycle_time_s"]
        assert d_cool == d_cycle
