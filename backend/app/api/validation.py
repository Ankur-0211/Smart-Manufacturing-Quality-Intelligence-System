"""Registry-driven request validation (roadmap 8.5, 9.3.3; R2-P1 task 9).

Tier 1 (box): Pydantic models whose field bounds are generated from the registry with
``create_model`` — the registry stays the single source of every limit (rule B6).
Tier 2 (couplings): ``ConstraintRegistry.check_couplings`` on the validated values plus the run
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
from app.contracts.enums import ParameterKind
from app.domain.constraint_loader import ConstraintRegistry, ParameterSpec
from app.schemas.envelope import ErrorDetail

_MODEL_NAMES = {
    ParameterKind.SETPOINT: "ProcessRecipeIn",
    ParameterKind.LOT_ATTRIBUTE: "MaterialLotAttributesIn",
    ParameterKind.PRODUCT_CONTEXT: "ProductContextIn",
    ParameterKind.MACHINE_CONTEXT: "MachineContextIn",
}


def _field(spec: ParameterSpec) -> tuple[Any, Any]:
    unit = f" [{spec.unit}]" if spec.unit else ""
    description = f"{spec.display_name}{unit}"
    if spec.allowed_values is not None:
        literal = Literal[tuple(spec.allowed_values)]  # type: ignore[valid-type]
        return literal, Field(title=spec.display_name, description=description)
    py_type: type = int if spec.dtype == "int" else float
    extra: JsonDict | None = {"step": spec.step} if spec.step is not None else None
    return py_type, Field(
        ge=spec.min,
        le=spec.max,
        title=spec.display_name,
        description=description,
        json_schema_extra=extra,
    )


@lru_cache(maxsize=16)
def bounded_model(registry: ConstraintRegistry, kind: ParameterKind) -> type[BaseModel]:
    """A closed model with one bounded field per registry parameter of ``kind``.

    Cached per registry instance (the registry is immutable after load).
    """
    fields: dict[str, Any] = {spec.name: _field(spec) for spec in registry.parameters(kind)}
    model: type[BaseModel] = create_model(
        _MODEL_NAMES[kind],
        __config__=ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True),
        **fields,
    )
    return model


def recipe_model(registry: ConstraintRegistry) -> type[BaseModel]:
    return bounded_model(registry, ParameterKind.SETPOINT)


def _validate(
    registry: ConstraintRegistry, kind: ParameterKind, raw: Mapping[str, Any], loc: str
) -> dict[str, Any]:
    try:
        validated = bounded_model(registry, kind).model_validate(dict(raw))
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
    registry: ConstraintRegistry, values: Mapping[str, Any], loc: str
) -> ApiError | None:
    """Tier 2: one detail per violated coupling rule, attributed to its left-hand field."""
    breaches = registry.check_couplings(values)
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
        hint="Adjust the named parameters so every coupling rule in GET /constraints holds.",
    )


def validate_recipe(
    registry: ConstraintRegistry,
    raw: Mapping[str, Any],
    *,
    context: Mapping[str, Any] | None = None,
    loc: str = "parameters",
) -> dict[str, float]:
    """Validate a full ProcessRecipe: box bounds, then couplings with the run context.

    ``context`` carries the flat machine/product/lot values (e.g. ``max_inj_pressure_bar``)
    needed by couplings such as CPL-003/CPL-004. Raises ``ApiError`` (422) on any violation.
    """
    values = _validate(registry, ParameterKind.SETPOINT, raw, loc)
    error = coupling_error(registry, {**(context or {}), **values}, loc)
    if error is not None:
        raise error
    return values


def validate_lot_attributes(
    registry: ConstraintRegistry, raw: Mapping[str, Any], *, loc: str = ""
) -> dict[str, Any]:
    """Box-validate material lot attributes (``POST /materials``, R2-P3)."""
    return _validate(registry, ParameterKind.LOT_ATTRIBUTE, raw, loc)
