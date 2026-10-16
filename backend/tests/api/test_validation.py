"""Registry-driven validation helpers (roadmap 9.3.3 tiers 1-2, R2-P1 task 9)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import ApiError, register_exception_handlers
from app.api.validation import recipe_model, validate_lot_attributes, validate_recipe
from app.contracts.errors import LockedParameterError, ModelNotLoadedError
from app.contracts.recipe import RECIPE_FIELDS
from app.domain.constraint_loader import ConstraintRegistry

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURE = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"


@pytest.fixture(scope="module")
def registry() -> ConstraintRegistry:
    return ConstraintRegistry.load(DOMAIN / "constraints.yaml")


@pytest.fixture
def nominal() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text("utf-8"))
    return data


def _raises(fn: Any, *args: Any, **kw: Any) -> ApiError:
    with pytest.raises(ApiError) as exc:
        fn(*args, **kw)
    return exc.value


def test_recipe_model_bounds_come_from_the_registry(registry: ConstraintRegistry) -> None:
    schema = recipe_model(registry).model_json_schema()
    assert list(schema["properties"]) == list(RECIPE_FIELDS)
    melt = schema["properties"]["melt_temp_c"]
    assert (melt["minimum"], melt["maximum"], melt["step"]) == (180, 295, 1)
    assert set(schema["required"]) == set(RECIPE_FIELDS)
    assert recipe_model(registry) is recipe_model(registry)  # cached per registry


def test_changing_the_registry_changes_the_bounds(registry: ConstraintRegistry) -> None:
    raw = yaml.safe_load((DOMAIN / "constraints.yaml").read_text("utf-8"))
    changed = copy.deepcopy(raw)
    changed["parameters"]["melt_temp_c"]["max"] = 270
    other = ConstraintRegistry.from_mapping(changed)
    melt = recipe_model(other).model_json_schema()["properties"]["melt_temp_c"]
    assert melt["maximum"] == 270


def test_valid_recipe_passes(registry: ConstraintRegistry, nominal: dict[str, Any]) -> None:
    flat_context = {**nominal["context"]["machine"]}
    values = validate_recipe(registry, nominal["recipe"], context=flat_context)
    assert values == {k: float(v) for k, v in nominal["recipe"].items()}


def test_out_of_range_is_param_out_of_range_with_details(
    registry: ConstraintRegistry, nominal: dict[str, Any]
) -> None:
    recipe = {**nominal["recipe"], "melt_temp_c": 300, "screw_rpm": 10}
    err = _raises(validate_recipe, registry, recipe)
    assert err.status_code == 422 and err.code == "PARAM_OUT_OF_RANGE"
    assert err.constraint_version == registry.version
    details = {d.field: d for d in err.details or []}
    assert set(details) == {"parameters.melt_temp_c", "parameters.screw_rpm"}
    assert (details["parameters.melt_temp_c"].limit, details["parameters.melt_temp_c"].value) == (
        295,
        300,
    )


def test_unknown_and_missing_fields(registry: ConstraintRegistry, nominal: dict[str, Any]) -> None:
    err = _raises(validate_recipe, registry, {**nominal["recipe"], "warp_knob": 1})
    assert err.code == "UNKNOWN_PARAMETER"
    recipe = dict(nominal["recipe"])
    del recipe["cushion_mm"]
    err = _raises(validate_recipe, registry, recipe)
    assert err.code == "VALIDATION_ERROR" and err.field == "parameters.cushion_mm"
    err = _raises(validate_recipe, registry, {**nominal["recipe"], "melt_temp_c": float("nan")})
    assert err.status_code == 422


def test_couplings_are_tier_two(registry: ConstraintRegistry, nominal: dict[str, Any]) -> None:
    recipe = {**nominal["recipe"], "hold_pressure_bar": 1000, "inj_pressure_bar": 900}
    err = _raises(validate_recipe, registry, recipe)
    assert err.code == "COUPLING_VIOLATION"
    (detail,) = err.details or []
    assert detail.field == "parameters.hold_pressure_bar"
    assert detail.message.startswith("CPL-001")
    assert (detail.value, detail.limit) == (1000, 900)


def test_machine_couplings_use_the_context(
    registry: ConstraintRegistry, nominal: dict[str, Any]
) -> None:
    recipe = {**nominal["recipe"], "inj_pressure_bar": 1700}
    validate_recipe(registry, recipe)  # without machine context CPL-004 cannot be evaluated
    err = _raises(validate_recipe, registry, recipe, context={"max_inj_pressure_bar": 1600})
    assert [d.message[:7] for d in err.details or []] == ["CPL-004"]


def test_hard_constraints_are_not_rejected_here(
    registry: ConstraintRegistry, nominal: dict[str, Any]
) -> None:
    # 290 C is inside the box (<= 295) but above the PP-H ceiling (285): a BLOCKED stage at
    # runtime, never a 422 (roadmap 7.10 / 9.3.3).
    validate_recipe(registry, {**nominal["recipe"], "melt_temp_c": 290})


def test_lot_attributes(registry: ConstraintRegistry) -> None:
    lot = {
        "resin_grade": "PP-H",
        "mfi": 12,
        "moisture_pct": 0.04,
        "regrind_pct": 15,
        "colourant_pct": 2,
    }
    assert validate_lot_attributes(registry, lot)["mfi"] == 12.0
    err = _raises(validate_lot_attributes, registry, {**lot, "resin_grade": "ABS"})
    assert err.field == "resin_grade"


def test_intelligence_errors_map_to_the_envelope() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/locked")
    def locked() -> None:
        raise LockedParameterError("moisture_pct is not actionable", field="moisture_pct")

    @app.get("/model")
    def model() -> None:
        raise ModelNotLoadedError("fusion bundle missing", hint="run R1-P4")

    with TestClient(app) as c:
        resp = c.get("/locked")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "PARAMETER_NOT_ACTIONABLE"
        assert resp.json()["error"]["field"] == "moisture_pct"
        resp = c.get("/model")
        assert resp.status_code == 503 and resp.json()["error"]["hint"] == "run R1-P4"
