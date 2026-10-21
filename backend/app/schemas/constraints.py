"""``GET /api/v1/constraints`` payload (roadmap 8.4, 9.3.2).

Built from Role 1's ``ConstraintRegistry.to_public_dict()``. The fields the UI relies on are typed
so the frontend can generate its types; any further keys Role 1 adds pass through unchanged
(``extra="allow"``). The frontend builds every slider, bound, step and unit from this (rule B6).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.domain.constraint_loader import ConstraintRegistry


class _Open(BaseModel):
    model_config = ConfigDict(extra="allow")


class ParameterSpecOut(_Open):
    name: str
    kind: str
    stage: str | None = None
    unit: str | None = None
    dtype: str = "float"
    min: float | None = None
    max: float | None = None
    nominal: float | str | None = None
    step: float | None = None
    tolerance: float | None = None
    actionable: bool = False
    change_cost: float | None = None
    max_step_change: float | None = None
    display_name: str
    provenance: str | None = None
    citation: str | None = None


class CouplingRuleOut(_Open):
    id: str
    description: str
    params: list[str]
    severity: str
    message: str | None = None


class HardConstraintOut(_Open):
    id: str
    stage: str
    blocks_stage: bool
    severity_in_simulation: str
    enforced_in_guard: bool
    description: str


class ResinGradeOut(_Open):
    name: str | None = None
    melt_window_c: list[float] | None = None
    degradation_ceiling_c: float | None = None
    moisture_spec_max_pct: float | None = None
    moisture_critical_factor: float | None = None
    mfi_nominal: float | None = None
    provenance: str | None = None
    citation: str | None = None


class RiskBandsOut(_Open):
    stage_health: dict[str, float]
    p_fail: dict[str, float]


class ConstraintsOut(_Open):
    version: str  # roadmap 9.3.2: to_public_dict() + version + content_hash
    registry_version: str
    content_hash: str
    parameters: list[ParameterSpecOut]  # registry order, with the parameter name
    coupling_rules: list[CouplingRuleOut]
    hard_constraints: list[HardConstraintOut]
    resin_grades: dict[str, ResinGradeOut]
    risk_bands: RiskBandsOut


def public_constraints(registry: ConstraintRegistry) -> ConstraintsOut:
    public: dict[str, Any] = dict(registry.to_public_dict())
    parameters = public.pop("parameters", {})
    return ConstraintsOut.model_validate(
        {
            **public,
            "version": registry.version,
            "parameters": [{**spec, "name": name} for name, spec in parameters.items()],
        }
    )
