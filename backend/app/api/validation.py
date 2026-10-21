"""Registry-driven request validation (roadmap 8.5, 9.3.3; R2-P1 task 9).

Tier 1 (box): Pydantic models whose field bounds are generated from Role 1's registry with
``create_model`` — the registry stays the single source of every limit (rule B6).
Tier 2 (couplings): Role 1's ``ConstraintRegistry.check_couplings(recipe, context)`` with the run
context (machine maxima). Both tiers answer HTTP 422 with per-field ``details``.
Hard constraints are NOT checked here: they are runtime domain rules (BLOCKED, not rejected).
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from pydantic.config import JsonDict

from app.api.errors import ApiError, ErrorCode, validation_error_to_api_error
from app.contracts.context import RunContext
from app.contracts.recipe import ProcessRecipe
from app.domain.constraint_loader import ConstraintRegistry
from app.schemas.envelope import ErrorDetail

_STRICT = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
# MaterialLot attributes (contract fields). Role 1's registry has no windows for them yet
# (CCR-004); they get bounds automatically once registry entries exist.
LOT_ATTRIBUTES = ("mfi", "moisture_pct", "regrind_pct", "colourant_pct")


def _bounded_field(name: str, spec: Mapping[str, Any]) -> tuple[Any, Any]:
    display = str(spec.get("display_name", name))
    unit = f" [{spec['unit']}]" if spec.get("unit") else ""
    py_type: type = int if spec.get("dtype") == "int" else float
    extra: JsonDict | None = {"step": spec["step"]} if spec.get("step") is not None else None
    return py_type, Field(
        ge=spec.get("min"),
        le=spec.get("max"),
        title=display,
        description=f"{display}{unit}",
        json_schema_extra=extra,
    )


@lru_cache(maxsize=16)
def recipe_model(registry: ConstraintRegistry) -> type[BaseModel]:
    """A closed model with one bounded field per registry setpoint (cached per registry)."""
    fields: dict[str, Any] = {
        name: _bounded_field(name, spec)
        for name, spec in registry.parameters.items()
        if spec.get("kind", "setpoint") == "setpoint"
    }
    model: type[BaseModel] = create_model("ProcessRecipeIn", __config__=_STRICT, **fields)
    return model


@lru_cache(maxsize=16)
def lot_model(registry: ConstraintRegistry) -> type[BaseModel]:
    """MaterialLot attributes: resin grade from the registry's grades, windows where defined."""
    grades = tuple(registry.resin_grades)
    fields: dict[str, Any] = {
        "resin_grade": (Literal[grades], Field(description="Key of the registry resin_grades")),
    }
    for name in LOT_ATTRIBUTES:
        spec = registry.get_parameter(name)
        fields[name] = _bounded_field(name, spec) if spec is not None else (float, Field())
    model: type[BaseModel] = create_model("MaterialLotAttributesIn", __config__=_STRICT, **fields)
    return model


def _validate(
    registry: ConstraintRegistry, model: type[BaseModel], raw: Mapping[str, Any], loc: str
) -> dict[str, Any]:
    try:
        validated = model.model_validate(dict(raw))
    except ValidationError as exc:
        prefix = (loc,) if loc else ()
        errors = [
            {**err, "loc": (*prefix, *err["loc"])}
            for err in exc.errors(include_url=False, include_context=True)
        ]
        api_error = validation_error_to_api_error(errors)
        api_error.constraint_version = registry.version
        raise api_error from None
    values: dict[str, Any] = validated.model_dump()
    return values


def coupling_error(
    registry: ConstraintRegistry,
    recipe: Mapping[str, float],
    context: Mapping[str, Any],
    loc: str,
) -> ApiError | None:
    """Tier 2: one detail per violated coupling rule, attributed to its first parameter."""
    breaches = registry.check_couplings(
        ProcessRecipe.model_validate(dict(recipe)), RunContext.model_validate(dict(context))
    )
    if not breaches:
        return None
    details = [
        ErrorDetail(
            field=f"{loc}.{b.parameters[0]}" if loc else b.parameters[0],
            code=ErrorCode.COUPLING_VIOLATION.value,
            message=f"{b.rule_id}: {b.message}",
            limit=b.limit,
            value=b.value,
        )
        for b in breaches
    ]
    first = details[0]
    return ApiError(
        ErrorCode.COUPLING_VIOLATION,
        first.message if len(details) == 1 else f"{len(details)} coupling rules violated",
        field=first.field,
        details=details,
        constraint_version=registry.version,
        hint=breaches[0].hint
        or "Adjust the named parameters so every coupling rule in GET /constraints holds.",
    )


def validate_recipe(
    registry: ConstraintRegistry,
    raw: Mapping[str, Any],
    *,
    context: Mapping[str, Any],
    loc: str = "parameters",
) -> dict[str, float]:
    """Validate a full ProcessRecipe: box bounds, then couplings with the run context.

    ``context`` is the run's RunContext JSON (machine/product/material_lot snapshot); couplings
    such as CPL-003/CPL-004 read the machine's limits from it. Raises ``ApiError`` (422).
    """
    values = _validate(registry, recipe_model(registry), raw, loc)
    error = coupling_error(registry, values, context, loc)
    if error is not None:
        raise error
    return values


def validate_lot_attributes(
    registry: ConstraintRegistry, raw: Mapping[str, Any], *, loc: str = ""
) -> dict[str, Any]:
    """Validate material lot attributes (``POST /materials``, R2-P3)."""
    return _validate(registry, lot_model(registry), raw, loc)
