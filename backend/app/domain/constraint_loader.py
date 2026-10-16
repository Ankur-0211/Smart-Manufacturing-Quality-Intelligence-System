"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

Constraint registry loader (roadmap 8.4). Pure, immutable after load, fail-fast: any structural
or cross-reference problem raises ``RegistryInvalidError`` so the backend refuses to start.

Rule evaluation is data-driven: the rule "kind" vocabulary is documented in the header of
``constraints.yaml``. This module holds NO limit values (roadmap 8.6).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.contracts.context import MachineProfile, MaterialLot, ProductContext
from app.contracts.enums import (
    INTELLIGENCE_STAGES,
    ConstraintSeverity,
    DataProvenance,
    ParameterKind,
    RiskLevel,
    StageName,
)
from app.contracts.errors import RegistryInvalidError, UnknownParameterError
from app.contracts.recipe import RECIPE_FIELDS
from app.contracts.stage import ConstraintBreach
from app.domain.dependency_graph import StageDependencyGraph

# Identity / categorical fields that are part of the contracts but carry no registry window.
_UNREGISTERED_CONTEXT_FIELDS = frozenset(
    {"machine_id", "machine_type", "product_id", "name", "material_lot_id"}
)


class _Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResinGradeSpec(_Spec):
    melt_window_c: tuple[float, float]
    degradation_ceiling_c: float
    moisture_spec_max_pct: float = Field(gt=0)
    moisture_critical_factor: float = Field(gt=0)
    mfi_nominal: float
    provenance: DataProvenance
    citation: str | None = None


class ParameterSpec(_Spec):
    name: str
    kind: ParameterKind
    stage: StageName | None
    unit: str | None
    dtype: Literal["float", "int", "category"]
    min: float | None = None
    max: float | None = None
    nominal: float | str | None = None
    step: float | None = Field(default=None, gt=0)
    tolerance: float | None = Field(default=None, gt=0)
    allowed_values: list[str | int] | None = None
    actionable: bool
    change_cost: float | None = Field(default=None, ge=0, le=1)
    max_step_change: float | None = Field(default=None, gt=0)
    policy_max: float | None = None
    display_name: str
    provenance: DataProvenance
    citation: str | None = None

    @model_validator(mode="after")
    def _window(self) -> ParameterSpec:
        if self.dtype == "category" or self.allowed_values is not None:
            if not self.allowed_values:
                raise ValueError(f"{self.name}: categorical parameters need allowed_values")
            return self
        if self.min is None or self.max is None or self.min > self.max:
            raise ValueError(f"{self.name}: numeric parameters need min <= max")
        if isinstance(self.nominal, (int, float)) and not self.min <= self.nominal <= self.max:
            raise ValueError(f"{self.name}: nominal outside [min, max]")
        if self.actionable and (self.change_cost is None or self.max_step_change is None):
            raise ValueError(f"{self.name}: actionable parameters need change_cost/max_step_change")
        if self.actionable and self.kind is not ParameterKind.SETPOINT:
            raise ValueError(f"{self.name}: only setpoints may be actionable (Plan 14.7)")
        return self


class CouplingRule(_Spec):
    id: str
    kind: Literal["le", "ge_offset"]
    left: str
    right: str
    offset: float = 0.0
    severity: ConstraintSeverity
    description: str
    provenance: DataProvenance = DataProvenance.UNVALIDATED


class HardConstraint(_Spec):
    id: str
    stage: StageName
    kind: Literal["max_from_grade", "max_from_grade_factor", "max_ratio", "min_derived", "range"]
    param: str
    grade_field: str | None = None
    factor_field: str | None = None
    derived: str | None = None
    other: str | None = None
    factor: float | None = None
    min: float | None = None
    max: float | None = None
    blocks_stage: bool
    severity_in_simulation: ConstraintSeverity
    enforced_in_guard: bool
    description: str
    hint: str | None = None
    provenance: DataProvenance = DataProvenance.UNVALIDATED

    @model_validator(mode="after")
    def _operands(self) -> HardConstraint:
        needed = {
            "max_from_grade": ("grade_field",),
            "max_from_grade_factor": ("grade_field", "factor_field"),
            "max_ratio": ("other", "factor"),
            "min_derived": ("derived",),
            "range": ("min", "max"),
        }[self.kind]
        missing = [f for f in needed if getattr(self, f) is None]
        if missing:
            raise ValueError(f"{self.id}: kind {self.kind} needs {', '.join(missing)}")
        if self.blocks_stage and self.severity_in_simulation is not ConstraintSeverity.CRITICAL:
            raise ValueError(f"{self.id}: only CRITICAL rules may block a stage")
        return self


class StageCheck(_Spec):
    check_id: str
    type: Literal["range", "zscore", "indicator"]
    target: str
    weight: float = Field(gt=0, le=1)
    provenance: DataProvenance


class RiskBands(_Spec):
    stage_health: dict[RiskLevel, float]  # lower bounds of health; below the last => CRITICAL
    p_fail: dict[RiskLevel, float]  # lower bounds of p_fail; below the first => NORMAL

    @model_validator(mode="after")
    def _monotone(self) -> RiskBands:
        health = [self.stage_health[r] for r in _HEALTH_BANDS if r in self.stage_health]
        p_fail = [self.p_fail[r] for r in _P_FAIL_BANDS if r in self.p_fail]
        if len(health) != len(_HEALTH_BANDS) or health != sorted(health, reverse=True):
            raise ValueError("stage_health needs NORMAL > LOW > MEDIUM > HIGH lower bounds")
        if len(p_fail) != len(_P_FAIL_BANDS) or p_fail != sorted(p_fail):
            raise ValueError("p_fail needs LOW < MEDIUM < HIGH < CRITICAL lower bounds")
        return self


_HEALTH_BANDS = (RiskLevel.NORMAL, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH)
_P_FAIL_BANDS = (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL)


class RecommendationSettings(_Spec):
    default_max_changes: int = Field(ge=1, le=6)
    coordinate_levels: int = Field(ge=2)
    pairwise_top_k: int = Field(ge=1)
    stability_trials: int = Field(ge=1)
    stability_noise_fraction_of_step: float = Field(gt=0)
    max_unstable_flip_rate: float = Field(ge=0, le=1)
    weights: dict[str, float]
    cycle_time_follows_stage_times: bool


class Submodels(_Spec):
    enabled: bool


class RegistryDocument(_Spec):
    registry_version: str = Field(pattern=r"^constraints-\d+\.\d+\.\d+$")
    units_allowed: list[str]
    resin_grades: dict[str, ResinGradeSpec]
    stage_inputs: dict[StageName, list[str]]
    parameters: dict[str, ParameterSpec]
    coupling_rules: list[CouplingRule]
    hard_constraints: list[HardConstraint]
    stage_checks: dict[StageName, list[StageCheck]]
    risk_bands: RiskBands
    recommendation: RecommendationSettings
    submodels: Submodels

    @field_validator("parameters", mode="before")
    @classmethod
    def _inject_names(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: {**v, "name": k} if isinstance(v, dict) else v for k, v in value.items()}
        return value


def _expected_registry_fields() -> dict[ParameterKind, frozenset[str]]:
    def fields(model: type[BaseModel]) -> frozenset[str]:
        return frozenset(model.model_fields) - _UNREGISTERED_CONTEXT_FIELDS

    return {
        ParameterKind.SETPOINT: frozenset(RECIPE_FIELDS),
        ParameterKind.LOT_ATTRIBUTE: fields(MaterialLot),
        ParameterKind.PRODUCT_CONTEXT: fields(ProductContext),
        ParameterKind.MACHINE_CONTEXT: fields(MachineProfile),
    }


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class ConstraintRegistry:
    """Immutable view over a validated ``constraints.yaml``."""

    def __init__(self, document: RegistryDocument, content_hash: str) -> None:
        self._doc = document
        self.version: str = document.registry_version
        self.content_hash: str = content_hash
        self._graph = StageDependencyGraph(document.stage_inputs)
        self._cross_check()

    # ------------------------------------------------------------------ loading
    @classmethod
    def load(cls, path: Path) -> ConstraintRegistry:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise RegistryInvalidError(f"cannot read constraint registry {path}: {exc}") from exc
        return cls.from_mapping(raw)

    @classmethod
    def from_mapping(cls, raw: Any) -> ConstraintRegistry:
        if not isinstance(raw, dict):
            raise RegistryInvalidError("constraint registry must be a mapping")
        try:
            document = RegistryDocument.model_validate(raw)
        except ValidationError as exc:
            raise RegistryInvalidError(
                "constraint registry failed validation",
                details=exc.errors(include_url=False, include_context=False),
            ) from exc
        canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return cls(document, hashlib.sha256(canonical.encode("utf-8")).hexdigest())

    def _cross_check(self) -> None:
        doc, problems = self._doc, []
        params = doc.parameters
        for kind, expected in _expected_registry_fields().items():
            actual = {n for n, p in params.items() if p.kind is kind}
            if actual != expected:
                problems.append(
                    f"{kind.value} parameters differ from the contracts: "
                    f"missing {sorted(expected - actual)}, unexpected {sorted(actual - expected)}"
                )
        for name, p in params.items():
            if p.unit is not None and p.unit not in doc.units_allowed:
                problems.append(f"{name}: unit {p.unit!r} not in units_allowed")
            if p.stage != self._graph.first_stage(name):
                problems.append(
                    f"{name}: stage {p.stage} but stage_inputs first read it in "
                    f"{self._graph.first_stage(name)}"
                )
        unknown_inputs = self._graph.fields() - set(params)
        if unknown_inputs:
            problems.append(f"stage_inputs reference unknown fields {sorted(unknown_inputs)}")
        grades = params.get("resin_grade")
        if grades is None or set(grades.allowed_values or []) != set(doc.resin_grades):
            problems.append("resin_grade.allowed_values must equal the resin_grades keys")
        grade_fields = set(ResinGradeSpec.model_fields)
        for rule in doc.coupling_rules:
            problems += [
                f"{rule.id}: unknown parameter {f}"
                for f in (rule.left, rule.right)
                if f not in params
            ]
        for hc in doc.hard_constraints:
            refs = [hc.param, *([hc.other] if hc.other else [])]
            problems += [f"{hc.id}: unknown parameter {f}" for f in refs if f not in params]
            problems += [
                f"{hc.id}: unknown resin grade field {f}"
                for f in (hc.grade_field, hc.factor_field)
                if f is not None and f not in grade_fields
            ]
        for stage in INTELLIGENCE_STAGES:
            total = sum(c.weight for c in doc.stage_checks.get(stage, []))
            if not 0 < total <= 1 + 1e-9:
                problems.append(f"stage_checks {stage}: weights must sum to (0, 1], got {total}")
        if problems:
            raise RegistryInvalidError("constraint registry is inconsistent", details=problems)

    # ------------------------------------------------------------------ lookups
    @property
    def document(self) -> RegistryDocument:
        return self._doc

    @property
    def graph(self) -> StageDependencyGraph:
        return self._graph

    def parameter(self, name: str) -> ParameterSpec:
        try:
            return self._doc.parameters[name]
        except KeyError:
            raise UnknownParameterError(f"unknown parameter {name!r}", field=name) from None

    def parameters(self, kind: ParameterKind | None = None) -> list[ParameterSpec]:
        return [p for p in self._doc.parameters.values() if kind is None or p.kind is kind]

    def resin_grade(self, grade: str) -> ResinGradeSpec:
        try:
            return self._doc.resin_grades[grade]
        except KeyError:
            raise UnknownParameterError(
                f"unknown resin grade {grade!r}", field="resin_grade"
            ) from None

    def hard_constraint(self, rule_id: str) -> HardConstraint:
        for hc in self._doc.hard_constraints:
            if hc.id == rule_id:
                return hc
        raise KeyError(rule_id)

    def stage_inputs(self, stage: StageName) -> list[str]:
        return self._graph.stage_inputs(stage)

    def invalidated_stages(self, changed: Iterable[str]) -> list[StageName]:
        changed = list(changed)
        for name in changed:
            self.parameter(name)  # unknown names raise UnknownParameterError
        return self._graph.invalidated_stages(changed)

    # ------------------------------------------------------------------ checks
    def _breach(
        self,
        rule_id: str,
        severity: ConstraintSeverity,
        parameters: list[str],
        message: str,
        *,
        value: float | None = None,
        limit: float | None = None,
        hint: str | None = None,
        provenance: DataProvenance = DataProvenance.UNVALIDATED,
    ) -> ConstraintBreach:
        return ConstraintBreach(
            rule_id=rule_id,
            severity=severity,
            parameters=parameters,
            value=value,
            limit=limit,
            message=message,
            hint=hint,
            provenance=provenance,
            constraints_version=self.version,
        )

    def check_box(self, values: Mapping[str, Any]) -> list[ConstraintBreach]:
        """Tier 1: each known, present field within its window (HTTP 422 PARAM_OUT_OF_RANGE).

        Keys the registry does not know (ids, machine_type) are ignored; ``None`` means absent.
        """
        breaches: list[ConstraintBreach] = []
        for name, raw in values.items():
            spec = self._doc.parameters.get(name)
            if spec is None or raw is None:
                continue
            rule_id, crit = f"BOX:{name}", ConstraintSeverity.CRITICAL
            if spec.allowed_values is not None:
                if raw not in spec.allowed_values:
                    allowed = ", ".join(str(v) for v in spec.allowed_values)
                    breaches.append(
                        self._breach(
                            rule_id,
                            crit,
                            [name],
                            f"{name}={raw!r} is not one of: {allowed}",
                            provenance=spec.provenance,
                        )
                    )
                continue
            value = _as_float(raw)
            if value is None or (spec.dtype == "int" and not value.is_integer()):
                breaches.append(
                    self._breach(
                        rule_id,
                        crit,
                        [name],
                        f"{name} must be {spec.dtype}",
                        provenance=spec.provenance,
                    )
                )
                continue
            assert spec.min is not None and spec.max is not None  # guaranteed by ParameterSpec
            if not spec.min <= value <= spec.max:
                limit = spec.min if value < spec.min else spec.max
                unit = f" {spec.unit}" if spec.unit else ""
                breaches.append(
                    self._breach(
                        rule_id,
                        crit,
                        [name],
                        f"{name}={value:g} is outside [{spec.min:g}, {spec.max:g}]{unit}",
                        value=value,
                        limit=limit,
                        provenance=spec.provenance,
                    )
                )
        return breaches

    def check_couplings(self, values: Mapping[str, Any]) -> list[ConstraintBreach]:
        """Tier 2 cross-field rules (HTTP 422 COUPLING_VIOLATION; recommendation guard 3)."""
        breaches: list[ConstraintBreach] = []
        for rule in self._doc.coupling_rules:
            left, right = _as_float(values.get(rule.left)), _as_float(values.get(rule.right))
            if left is None or right is None:
                continue
            if rule.kind == "le":
                ok, limit = left <= right, right
            else:  # ge_offset
                limit = right + rule.offset
                ok = left >= limit
            if not ok:
                breaches.append(
                    self._breach(
                        rule.id,
                        rule.severity,
                        [rule.left, rule.right],
                        rule.description,
                        value=left,
                        limit=limit,
                        provenance=rule.provenance,
                    )
                )
        return breaches

    def check_hard_constraints(
        self,
        values: Mapping[str, Any],
        derived: Mapping[str, float] | None = None,
        *,
        stage: StageName | None = None,
    ) -> list[ConstraintBreach]:
        """Runtime domain/safety tier (BLOCKED or WARNING; recommendation guard 2).

        Rules whose operands are absent (e.g. a ``min_derived`` rule before the stage module has
        computed its value) are skipped, never guessed. ``stage`` limits the rules evaluated.
        """
        derived = derived or {}
        breaches: list[ConstraintBreach] = []
        for hc in self._doc.hard_constraints:
            if stage is not None and hc.stage is not stage:
                continue
            value = _as_float(values.get(hc.param))
            if value is None:
                continue
            result = self._evaluate_hard(hc, value, values, derived)
            if result is None:
                continue
            ok, limit, provenance = result
            if not ok:
                breaches.append(
                    self._breach(
                        hc.id,
                        hc.severity_in_simulation,
                        [hc.param, *([hc.other] if hc.other else [])],
                        hc.description,
                        value=value,
                        limit=limit,
                        hint=hc.hint,
                        provenance=provenance,
                    )
                )
        return breaches

    def _evaluate_hard(
        self,
        hc: HardConstraint,
        value: float,
        values: Mapping[str, Any],
        derived: Mapping[str, float],
    ) -> tuple[bool, float, DataProvenance] | None:
        if hc.kind in ("max_from_grade", "max_from_grade_factor"):
            grade = self._doc.resin_grades.get(str(values.get("resin_grade")))
            if grade is None:
                return None  # unknown grade is a box failure, reported by check_box
            limit = float(getattr(grade, str(hc.grade_field)))
            if hc.kind == "max_from_grade_factor":
                limit *= float(getattr(grade, str(hc.factor_field)))
            return value <= limit, limit, grade.provenance
        if hc.kind == "max_ratio":
            other = _as_float(values.get(str(hc.other)))
            if other is None:
                return None
            limit = float(hc.factor or 0) * other
            return value <= limit, limit, hc.provenance
        if hc.kind == "min_derived":
            required = derived.get(str(hc.derived))
            if required is None:
                return None
            return value >= required, float(required), hc.provenance
        # range
        assert hc.min is not None and hc.max is not None
        limit = hc.min if value < hc.min else hc.max
        return hc.min <= value <= hc.max, limit, hc.provenance

    # ------------------------------------------------------------------ public payload
    @cached_property
    def _public(self) -> dict[str, Any]:
        doc = self._doc.model_dump(mode="json", exclude={"registry_version"})
        doc["parameters"] = [p.model_dump(mode="json") for p in self._doc.parameters.values()]
        return {"version": self.version, "content_hash": self.content_hash, **doc}

    def to_public_dict(self) -> dict[str, Any]:
        """Payload of ``GET /api/v1/constraints``; the frontend builds every slider from it."""
        payload: dict[str, Any] = json.loads(json.dumps(self._public))  # defensive deep copy
        return payload
