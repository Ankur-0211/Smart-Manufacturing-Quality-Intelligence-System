"""Constraint loader and registry API (roadmap Section 8.4)."""
import hashlib
from pathlib import Path
from typing import Any
import yaml

from ..contracts.context import ProcessInput, RunContext
from ..contracts.enums import ConstraintSeverity, DataProvenance, StageName
from ..contracts.errors import RegistryInvalidError
from ..contracts.recipe import ProcessRecipe
from ..contracts.stage import ConstraintBreach


class ConstraintRegistry:
    """In-memory loaded constraint registry."""

    def __init__(self, raw_data: dict[str, Any], raw_yaml_text: str):
        self._data = raw_data
        self.version: str = raw_data.get("registry_version", "constraints-1.0.0")
        self.content_hash: str = hashlib.sha256(raw_yaml_text.encode("utf-8")).hexdigest()
        self.resin_grades: dict[str, Any] = raw_data.get("resin_grades", {})
        self.parameters: dict[str, Any] = raw_data.get("parameters", {})
        self.coupling_rules: list[dict[str, Any]] = raw_data.get("coupling_rules", [])
        self.hard_constraints: list[dict[str, Any]] = raw_data.get("hard_constraints", [])
        self.stage_checks: dict[str, Any] = raw_data.get("stage_checks", {})
        self.risk_bands: dict[str, Any] = raw_data.get("risk_bands", {})
        self.recommendation_cfg: dict[str, Any] = raw_data.get("recommendation", {})

    def to_public_dict(self) -> dict[str, Any]:
        """Dictionary returned by GET /api/v1/constraints."""
        return {
            "registry_version": self.version,
            "content_hash": self.content_hash,
            "parameters": self.parameters,
            "coupling_rules": self.coupling_rules,
            "hard_constraints": self.hard_constraints,
            "resin_grades": self.resin_grades,
            "risk_bands": self.risk_bands,
        }

    def get_parameter(self, param_name: str) -> dict[str, Any] | None:
        return self.parameters.get(param_name)

    def get_resin_grade(self, grade: str) -> dict[str, Any]:
        return self.resin_grades.get(grade, self.resin_grades.get("PP-H", {}))

    def check_box(self, param_name: str, value: float) -> tuple[bool, float, float]:
        """Check if value is within min and max box bounds."""
        param = self.parameters.get(param_name)
        if not param:
            return True, float("-inf"), float("inf")
        p_min = float(param.get("min", float("-inf")))
        p_max = float(param.get("max", float("inf")))
        return (p_min <= value <= p_max), p_min, p_max

    def stage_inputs(self, stage: StageName) -> list[str]:
        """Return parameter names whose first consuming stage is `stage`."""
        out: list[str] = []
        for name, spec in self.parameters.items():
            if spec.get("stage") == stage.value:
                out.append(name)
        return out

    def check_couplings(
        self, recipe: ProcessRecipe, context: RunContext
    ) -> list[ConstraintBreach]:
        """Evaluate tier-2 coupling rules across setpoints and machine limits."""
        breaches: list[ConstraintBreach] = []

        # CPL-001: hold_pressure_bar <= inj_pressure_bar
        if recipe.hold_pressure_bar > recipe.inj_pressure_bar:
            breaches.append(
                ConstraintBreach(
                    rule_id="CPL-001",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["hold_pressure_bar", "inj_pressure_bar"],
                    value=recipe.hold_pressure_bar,
                    limit=recipe.inj_pressure_bar,
                    message="Holding pressure cannot exceed injection pressure",
                    hint="Reduce hold_pressure_bar or increase inj_pressure_bar",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
            )

        # CPL-002: melt_temp_c >= mold_temp_c + 120
        delta = recipe.melt_temp_c - recipe.mold_temp_c
        if delta < 120.0:
            breaches.append(
                ConstraintBreach(
                    rule_id="CPL-002",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["melt_temp_c", "mold_temp_c"],
                    value=delta,
                    limit=120.0,
                    message="Melt-to-mold temperature delta is under 120 °C (risk of short shot / freeze-off)",
                    hint="Increase melt_temp_c or lower mold_temp_c",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
            )

        # CPL-003: clamp_force_ton <= max_clamp_force_ton
        if recipe.clamp_force_ton > context.machine.max_clamp_force_ton:
            breaches.append(
                ConstraintBreach(
                    rule_id="CPL-003",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["clamp_force_ton"],
                    value=recipe.clamp_force_ton,
                    limit=context.machine.max_clamp_force_ton,
                    message=f"Clamp force ({recipe.clamp_force_ton}t) exceeds machine maximum ({context.machine.max_clamp_force_ton}t)",
                    hint="Reduce clamp_force_ton or select a higher-tonnage machine",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
            )

        # CPL-004: inj_pressure_bar <= max_inj_pressure_bar
        if recipe.inj_pressure_bar > context.machine.max_inj_pressure_bar:
            breaches.append(
                ConstraintBreach(
                    rule_id="CPL-004",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["inj_pressure_bar"],
                    value=recipe.inj_pressure_bar,
                    limit=context.machine.max_inj_pressure_bar,
                    message=f"Injection pressure ({recipe.inj_pressure_bar} bar) exceeds machine limit ({context.machine.max_inj_pressure_bar} bar)",
                    hint="Reduce inj_pressure_bar",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
            )

        return breaches

    def check_hard_constraints(
        self,
        stage: StageName,
        inp: ProcessInput,
        indicators: dict[str, Any],
    ) -> tuple[list[ConstraintBreach], bool, str | None]:
        """Check runtime hard constraints for a specific stage.
        Returns (breaches, is_blocked, block_reason)."""
        breaches: list[ConstraintBreach] = []
        is_blocked = False
        block_reason: str | None = None
        grade = self.get_resin_grade(inp.context.material_lot.resin_grade)

        if stage == StageName.MATERIAL_CONDITIONING:
            # HC-006: moisture critical factor
            spec_max = float(grade.get("moisture_spec_max_pct", 0.10))
            crit_factor = float(grade.get("moisture_critical_factor", 2.0))
            crit_limit = spec_max * crit_factor
            if inp.context.material_lot.moisture_pct > crit_limit:
                b = ConstraintBreach(
                    rule_id="HC-006",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["moisture_pct"],
                    value=inp.context.material_lot.moisture_pct,
                    limit=crit_limit,
                    message=f"Moisture ({inp.context.material_lot.moisture_pct}%) exceeds 2x spec ({crit_limit}%). Severe splay / hydrolytic degradation imminent.",
                    hint="Redry resin or replace lot before production.",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
                breaches.append(b)
                is_blocked = True
                block_reason = b.message

        elif stage == StageName.PLASTICIZING:
            # HC-001: melt degradation ceiling
            ceiling = float(grade.get("degradation_ceiling_c", 285.0))
            if inp.recipe.melt_temp_c > ceiling:
                b = ConstraintBreach(
                    rule_id="HC-001",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["melt_temp_c"],
                    value=inp.recipe.melt_temp_c,
                    limit=ceiling,
                    message=f"Melt temperature ({inp.recipe.melt_temp_c} °C) exceeds polymer degradation ceiling ({ceiling} °C). Polymer degradation hazard.",
                    hint="Lower barrel zone temperatures and melt_temp_c.",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
                breaches.append(b)
                is_blocked = True
                block_reason = b.message

        elif stage == StageName.INJECTION:
            # HC-002: required clamp force
            # Estimated cavity pressure: P_cav ~ 0.35 * inj_pressure_bar (heuristic)
            # Area in cm2 = projected_area_cm2 * cavity_count
            # Force in ton = (P_cav * Area) / 1000 * 1.02
            cavity_pressure = float(indicators.get("cavity_pressure_estimate_bar", inp.recipe.inj_pressure_bar * 0.35))
            area_cm2 = inp.context.product.projected_area_cm2 * inp.context.product.cavity_count
            required_ton = (cavity_pressure * area_cm2) / 981.0 * 1.15  # 15% safety factor
            indicators["required_clamp_force_ton"] = round(required_ton, 1)

            if inp.recipe.clamp_force_ton < required_ton:
                b = ConstraintBreach(
                    rule_id="HC-002",
                    severity=ConstraintSeverity.CRITICAL,
                    parameters=["clamp_force_ton"],
                    value=inp.recipe.clamp_force_ton,
                    limit=round(required_ton, 1),
                    message=f"Clamp force ({inp.recipe.clamp_force_ton}t) below required tonnage ({round(required_ton, 1)}t). High flash / mold opening hazard.",
                    hint="Increase clamp_force_ton to match required hydraulic clamp resistance.",
                    provenance=DataProvenance.SPECIFICATION_DERIVED,
                    constraints_version=self.version,
                )
                breaches.append(b)
                is_blocked = True
                block_reason = b.message

            # HC-003: Headroom warning
            headroom_limit = 0.90 * inp.context.machine.max_inj_pressure_bar
            if inp.recipe.inj_pressure_bar > headroom_limit:
                breaches.append(
                    ConstraintBreach(
                        rule_id="HC-003",
                        severity=ConstraintSeverity.WARNING,
                        parameters=["inj_pressure_bar"],
                        value=inp.recipe.inj_pressure_bar,
                        limit=round(headroom_limit, 1),
                        message=f"Injection pressure ({inp.recipe.inj_pressure_bar} bar) exceeds 90% of machine rating ({round(headroom_limit, 1)} bar).",
                        hint="Increase injection velocity or melt temperature to lower hydraulic peak pressure.",
                        provenance=DataProvenance.SPECIFICATION_DERIVED,
                        constraints_version=self.version,
                    )
                )

        elif stage == StageName.PACKING:
            # HC-005: Cushion check (2.0 to 15.0 mm)
            if inp.recipe.cushion_mm < 2.0 or inp.recipe.cushion_mm > 15.0:
                breaches.append(
                    ConstraintBreach(
                        rule_id="HC-005",
                        severity=ConstraintSeverity.WARNING,
                        parameters=["cushion_mm"],
                        value=inp.recipe.cushion_mm,
                        limit=2.0 if inp.recipe.cushion_mm < 2.0 else 15.0,
                        message=f"Cushion position ({inp.recipe.cushion_mm} mm) outside optimal packing range [2.0, 15.0] mm.",
                        hint="Adjust shot size or switchover position to stabilize cushion.",
                        provenance=DataProvenance.SPECIFICATION_DERIVED,
                        constraints_version=self.version,
                    )
                )

        elif stage == StageName.COOLING:
            # HC-004: minimum cooling time
            # t_cool ~ (s^2 / (pi^2 * alpha)) * ln(...) -> approx 2.0 * wall_thickness^2 for PP
            min_cooling = 2.0 * (inp.context.product.wall_thickness_mm ** 2)
            indicators["required_cooling_estimate_s"] = round(min_cooling, 1)
            if inp.recipe.cooling_time_s < min_cooling:
                breaches.append(
                    ConstraintBreach(
                        rule_id="HC-004",
                        severity=ConstraintSeverity.WARNING,
                        parameters=["cooling_time_s"],
                        value=inp.recipe.cooling_time_s,
                        limit=round(min_cooling, 1),
                        message=f"Cooling time ({inp.recipe.cooling_time_s}s) is below thermal solidification minimum ({round(min_cooling, 1)}s). Warpage / deformation risk.",
                        hint="Increase cooling_time_s or lower mold_temp_c.",
                        provenance=DataProvenance.SPECIFICATION_DERIVED,
                        constraints_version=self.version,
                    )
                )

        return breaches, is_blocked, block_reason


def load_constraint_registry(yaml_path: str | Path | None = None) -> ConstraintRegistry:
    """Load and parse constraints.yaml."""
    if yaml_path is None:
        yaml_path = Path(__file__).parent / "constraints.yaml"
    else:
        yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise RegistryInvalidError(f"Constraint file not found: {yaml_path}")

    try:
        content = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            raise RegistryInvalidError("Invalid YAML: top-level must be a dictionary")
        return ConstraintRegistry(data, content)
    except Exception as exc:
        raise RegistryInvalidError(f"Failed to load constraint registry: {exc}") from exc
