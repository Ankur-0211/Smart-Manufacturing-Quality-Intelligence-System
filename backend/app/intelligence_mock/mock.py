"""MockQualityIntelligence (roadmap 9.2, R2-P1 task 8).

Rules this module follows:
- It implements Role 1's ``QualityIntelligence`` Protocol (``app.contracts.interface``) and builds
  every output through the contract constructors, so any schema drift fails here first.
- Every number is a PLACEHOLDER derived from a SHA-256 of the canonical input. Nothing imitates
  real model or process behaviour; there is deliberately no hand-written physics.
- The BLOCKED path is driven only by Role 1's ``ConstraintRegistry.check_hard_constraints``;
  recommendation guards use its ``check_box`` and ``check_couplings``. No rule is re-implemented.
- Every prediction carries ``inference_backend="mock"``, ``is_mock=true``,
  ``model_version="mock-0.0.0"`` and the ``MOCK_INFERENCE`` caveat.

It may import ``app.contracts`` and ``app.domain`` only (R2-P1 compatibility requirement).
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from app.contracts.context import ProcessInput
from app.contracts.enums import (
    INTELLIGENCE_STAGES,
    AnomalyMethod,
    CandidateFlag,
    ConstraintSeverity,
    DataProvenance,
    InferenceBackend,
    PredictionLabel,
    RiskLevel,
    StageName,
    StageSubstate,
)
from app.contracts.errors import (
    InvalidInputError,
    LockedParameterError,
    StageResultsIncompleteError,
    UnknownParameterError,
    UpstreamMissingError,
)
from app.contracts.explanation import (
    FeatureAttribution,
    GlobalAttributionItem,
    GlobalExplanation,
    GroupedAttribution,
    LocalExplanation,
    StageRiskShare,
)
from app.contracts.interface import IntelligenceVersionInfo, PipelineResult
from app.contracts.prediction import CaveatItem, PredictionResult, RiskDriver
from app.contracts.recommendation import (
    GuardCheck,
    ParameterChange,
    RecommendationCandidate,
    RecommendationRequest,
    RecommendationResponse,
    StabilityReport,
    StageHealthAfter,
)
from app.contracts.sensitivity import SensitivityPoint, SensitivityResult
from app.contracts.stage import ConstraintBreach, StageAnomaly, StageResult, UpstreamContext
from app.contracts.version import CONTRACTS_VERSION
from app.domain.constraint_loader import ConstraintRegistry, load_constraint_registry

MOCK_VERSION = "mock-0.0.0"
MOCK_THRESHOLD = 0.5  # stands in for a bundle's metadata.json threshold
MOCK_ANOMALY_CUTOFF = 0.95  # stage anomaly flag when the placeholder score reaches this
FEATURE_SCHEMA_HASH = hashlib.sha256(b"mock-feature-schema-0.0.0").hexdigest()
MOCK_NOTE = "MOCK: placeholder output, not a model or rule evaluation."
# Capability keys as reported by Role 1's RealQualityIntelligence.capabilities().
CAPABILITIES: dict[str, bool] = {
    "run_stage": True,
    "predict": True,
    "explain": True,
    "global_explanation": True,
    "evaluate": True,
    "recommend": True,
    "sensitivity": True,
    "spc_check": False,  # P1; not part of Role 1's Protocol yet (CCR-004)
}

S = StageName
# Raw input slice each stage reads (roadmap 7.10). Only seeds the placeholders and fills
# ``inputs_used``; no limit or rule lives here.
STAGE_SLICE: dict[StageName, tuple[str, ...]] = {
    S.MATERIAL_CONDITIONING: (
        "moisture_pct",
        "mfi",
        "regrind_pct",
        "drying_time_h",
        "dryer_temp_c",
        "resin_grade",
        "colourant_pct",
    ),
    S.PLASTICIZING: (
        "barrel_temp_rear_c",
        "barrel_temp_mid_c",
        "barrel_temp_front_c",
        "nozzle_temp_c",
        "melt_temp_c",
        "screw_rpm",
        "back_pressure_bar",
        "residence_time_s",
        "mfi",
        "moisture_pct",
        "resin_grade",
    ),
    S.INJECTION: (
        "inj_velocity_mm_s",
        "inj_pressure_bar",
        "fill_time_s",
        "shot_size_mm",
        "switchover_position_mm",
        "clamp_force_ton",
        "max_inj_pressure_bar",
        "max_clamp_force_ton",
        "projected_area_cm2",
        "cavity_count",
    ),
    S.PACKING: (
        "hold_pressure_bar",
        "hold_time_s",
        "cushion_mm",
        "wall_thickness_mm",
        "mold_temp_c",
    ),
    S.COOLING: (
        "mold_temp_c",
        "cooling_time_s",
        "wall_thickness_mm",
        "cycle_time_s",
        "ejection_force_proxy",
        "fill_time_s",
        "hold_time_s",
    ),
}
# Upstream keys each stage needs (roadmap 7.10 "Upstream in").
REQUIRED_UPSTREAM: dict[StageName, tuple[str, ...]] = {
    S.MATERIAL_CONDITIONING: (),
    S.PLASTICIZING: ("viscosity_class", "moisture_flag"),
    S.INJECTION: ("effective_melt_temp_c", "viscosity_proxy"),
    S.PACKING: ("fill_completion_proxy", "cavity_pressure_estimate_bar", "effective_melt_temp_c"),
    S.COOLING: ("residual_stress_proxy", "effective_melt_temp_c"),
}
# Fixed indicator keys per stage (roadmap 7.10).
INDICATOR_KEYS: dict[StageName, tuple[str, ...]] = {
    S.MATERIAL_CONDITIONING: (
        "dryness_margin",
        "mfi_z",
        "moisture_z",
        "moisture_risk",
        "regrind_margin",
        "viscosity_class",
    ),
    S.PLASTICIZING: (
        "thermal_exposure",
        "degradation_exposure",
        "shear_heat_offset_c",
        "effective_melt_temp_c",
        "temp_profile_slope",
        "profile_monotonic",
        "splay_risk",
        "melt_consistency",
    ),
    S.INJECTION: (
        "fill_index",
        "shear_rate_proxy",
        "pressure_headroom",
        "cavity_pressure_estimate_bar",
        "required_clamp_force_ton",
        "short_shot_risk",
        "flash_risk",
        "fill_completion_proxy",
    ),
    S.PACKING: (
        "packing_integral",
        "gate_freeze_estimate_s",
        "hold_vs_freeze_ratio",
        "sink_void_risk",
        "over_pack_risk",
        "cushion_ok",
        "residual_stress_proxy",
    ),
    S.COOLING: (
        "required_cooling_estimate_s",
        "cooling_adequacy",
        "warp_risk",
        "ejection_risk",
        "dimensional_stability_index",
        "cycle_consistency",
        "cycle_balance",
    ),
}
_BOOL_INDICATORS = frozenset({"profile_monotonic", "cushion_ok"})
_NULL_INDICATORS = frozenset({"melt_consistency"})  # learned, P1: null in the MVP
# Indicators the registry's hard-constraint check computes itself (Role 1 heuristics).
_REGISTRY_INDICATORS = frozenset({"required_clamp_force_ton", "required_cooling_estimate_s"})
_CYCLE_FOLLOWS = ("fill_time_s", "hold_time_s", "cooling_time_s")  # UD-09
GuardName = Literal[
    "box", "hard_constraints", "couplings", "distribution", "step_size", "stability"
]
OptionLabel = Literal["Minimal change", "Balanced", "Aggressive"]
_OPTION_LABELS: tuple[OptionLabel, OptionLabel, OptionLabel] = (
    "Minimal change",
    "Balanced",
    "Aggressive",
)


def _unit(*parts: Any) -> float:
    """Deterministic placeholder in [0, 1) from the canonical JSON of ``parts``."""
    canonical = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return int(hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:13], 16) / 16**13


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class MockQualityIntelligence:
    """Deterministic, stateless placeholder implementation of ``QualityIntelligence``."""

    def __init__(self, registry: ConstraintRegistry) -> None:
        self.registry = registry

    @classmethod
    def for_tests(cls) -> MockQualityIntelligence:
        return cls(load_constraint_registry())

    # ------------------------------------------------------------------ meta
    def capabilities(self) -> dict[str, bool]:
        return dict(CAPABILITIES)

    def version_info(self) -> IntelligenceVersionInfo:
        return IntelligenceVersionInfo(
            contracts_version=CONTRACTS_VERSION,
            constraints_version=self.registry.version,
            model_version=MOCK_VERSION,
            is_mock=True,
            capabilities=self.capabilities(),
        )

    # ------------------------------------------------------------------ registry helpers
    def _spec(self, name: str) -> dict[str, Any]:
        spec = self.registry.get_parameter(name)
        if spec is None:
            raise UnknownParameterError(f"unknown parameter {name!r}", field=name)
        return spec

    def _health_band(self, health: float) -> RiskLevel:
        bands = self.registry.risk_bands.get("stage_health", {})
        for level in (RiskLevel.NORMAL, RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH):
            if health >= float(bands.get(level.value, 2.0)):
                return level
        return RiskLevel.CRITICAL

    def _p_fail_band(self, p_fail: float) -> RiskLevel:
        bands = self.registry.risk_bands.get("p_fail", {})
        band = RiskLevel.NORMAL
        for level in (RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL):
            if p_fail >= float(bands.get(level.value, 2.0)):
                band = level
        return band

    # ------------------------------------------------------------------ stages
    def run_stage(
        self, stage: StageName, inp: ProcessInput, upstream: UpstreamContext
    ) -> StageResult:
        t0 = time.perf_counter()
        if stage not in INTELLIGENCE_STAGES:
            raise InvalidInputError(f"run_stage covers S1-S5 only, got {stage}", field="stage")
        missing = [k for k in REQUIRED_UPSTREAM[stage] if getattr(upstream, k) is None]
        if missing:
            raise UpstreamMissingError(
                f"{stage} needs upstream keys {', '.join(missing)}", details=missing
            )
        flat = inp.flat()
        inputs_used = {k: flat.get(k) for k in STAGE_SLICE[stage]}
        seed = (stage.value, inputs_used, upstream.model_dump(mode="json"))

        upstream_out = self._upstream_out(stage, upstream, flat, seed)
        out_json = upstream_out.model_dump(mode="json")
        indicators: dict[str, Any] = {}
        for key in INDICATOR_KEYS[stage]:
            if key in _REGISTRY_INDICATORS:
                continue
            if key in out_json:
                indicators[key] = out_json[key]
            elif key in _NULL_INDICATORS:
                indicators[key] = None
            elif key in _BOOL_INDICATORS:
                indicators[key] = _unit(seed, key) >= 0.2
            else:
                indicators[key] = round(_unit(seed, key), 4)

        # Role 1's registry decides breaches and blocking. It reads/adds indicators of its own
        # (e.g. required clamp force); the mock's placeholder cavity pressure is not passed in.
        registry_indicators: dict[str, Any] = {}
        breaches, blocked, block_reason = self.registry.check_hard_constraints(
            stage, inp, registry_indicators
        )
        indicators.update(registry_indicators)

        health = round(0.35 + 0.65 * _unit(seed, "health"), 4)
        risk = self._health_band(health)
        if any(b.severity is ConstraintSeverity.CRITICAL for b in breaches):
            risk = RiskLevel.CRITICAL
        score = round(_unit(seed, "anomaly"), 4)
        flagged = score >= MOCK_ANOMALY_CUTOFF
        numeric_inputs = [k for k, v in inputs_used.items() if _numeric(v) is not None]
        contributors = (
            [{"feature": numeric_inputs[0], "deviation": round(4 * score, 3)}]
            if flagged and numeric_inputs
            else []
        )
        return StageResult(
            stage_name=stage,
            sequence_index=stage.sequence_index,
            substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
            inputs_used=inputs_used,
            upstream_in=upstream,
            upstream_out=upstream_out,
            health_score=health,
            risk_level=risk,
            risk_ordinal=risk.ordinal,
            anomaly=StageAnomaly(
                flag=flagged,
                score=score,
                method=AnomalyMethod.ZSCORE,
                contributors=contributors,
                note=MOCK_NOTE,
            ),
            indicators=indicators,
            indicator_provenance={k: DataProvenance.UNVALIDATED for k in indicators},
            notes=[MOCK_NOTE],
            constraint_breaches=breaches,
            blocked=blocked,
            block_reason=block_reason,
            module_version=MOCK_VERSION,
            constraints_version=self.registry.version,
            compute_ms=round((time.perf_counter() - t0) * 1000, 3),
        )

    def _upstream_out(
        self, stage: StageName, upstream: UpstreamContext, flat: Mapping[str, Any], seed: Any
    ) -> UpstreamContext:
        """Cumulative upstream: this stage adds only the keys it owns (7.8). Values are
        placeholders; the melt temperature passes the raw setpoint through unchanged."""
        add: dict[str, Any] = {}
        if stage is S.MATERIAL_CONDITIONING:
            add = {
                "viscosity_class": ("LOW", "NOMINAL", "HIGH")[int(_unit(seed, "visc") * 3)],
                "moisture_flag": _unit(seed, "moist") >= 0.8,
            }
        elif stage is S.PLASTICIZING:
            add = {
                "effective_melt_temp_c": float(flat["melt_temp_c"]),
                "viscosity_proxy": round(_unit(seed, "vproxy"), 4),
            }
        elif stage is S.INJECTION:
            add = {
                "fill_completion_proxy": round(_unit(seed, "fill"), 4),
                "cavity_pressure_estimate_bar": round(
                    float(flat["inj_pressure_bar"]) * _unit(seed, "cav"), 1
                ),
            }
        elif stage is S.PACKING:
            add = {"residual_stress_proxy": round(_unit(seed, "stress"), 4)}
        return upstream.model_copy(update=add)

    def _run_all_stages(self, inp: ProcessInput) -> list[StageResult]:
        results: list[StageResult] = []
        upstream = UpstreamContext()
        for stage in INTELLIGENCE_STAGES:
            result = self.run_stage(stage, inp, upstream)
            results.append(result)
            upstream = result.upstream_out
        return results

    # ------------------------------------------------------------------ fusion
    @staticmethod
    def _require_complete(stage_results: Sequence[StageResult]) -> None:
        if [r.stage_name for r in stage_results] != list(INTELLIGENCE_STAGES):
            raise StageResultsIncompleteError(
                "predict needs the five stage results S1-S5 in order",
                details=[r.stage_name.value for r in stage_results],
            )

    @staticmethod
    def _stage_shares(stage_results: Sequence[StageResult]) -> list[StageRiskShare]:
        weights = [(1.0 - r.health_score) + 1e-3 for r in stage_results]
        total = sum(weights)
        shares = [w / total for w in weights]
        shares[-1] = max(0.0, 1.0 - sum(shares[:-1]))
        return [
            StageRiskShare(stage=r.stage_name, share=s)
            for r, s in zip(stage_results, shares, strict=True)
        ]

    def predict(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        include_explanation: bool = True,
    ) -> PredictionResult:
        t0 = time.perf_counter()
        self._require_complete(stage_results)
        flat = inp.flat()
        healths = [r.health_score for r in stage_results]
        p_fail = round(_unit("predict", flat, healths), 4)
        label = PredictionLabel.FAIL if p_fail >= MOCK_THRESHOLD else PredictionLabel.PASS

        critical: list[ConstraintBreach] = [
            b
            for r in stage_results
            for b in r.constraint_breaches
            if b.severity is ConstraintSeverity.CRITICAL
        ]
        overridden = any(r.blocked for r in stage_results)
        risk = RiskLevel.CRITICAL if critical else self._p_fail_band(p_fail)
        drivers = [RiskDriver(source="model", detail=f"MOCK p_fail {p_fail:.2f}", weight=p_fail)]
        drivers += [
            RiskDriver(source="constraint", detail=f"{b.rule_id}: {b.message}", weight=1.0)
            for b in critical
        ]
        caveats = [CaveatItem(code="MOCK_INFERENCE", message="Placeholder output, not a model")]
        if critical:
            caveats.append(
                CaveatItem(
                    code="CRITICAL_CONSTRAINT_OVERRIDDEN",
                    message="NOT RELEASABLE: a critical constraint was breached",
                    features=sorted({p for b in critical for p in b.parameters}),
                )
            )
        flagged = [r.stage_name.value for r in stage_results if r.anomaly.flag]
        if flagged:
            caveats.append(
                CaveatItem(
                    code="ANOMALY_DETECTED", message="Stage anomaly flagged", features=flagged
                )
            )
        return PredictionResult(
            label=label,
            p_fail=p_fail,
            p_fail_raw=p_fail,
            threshold_used=MOCK_THRESHOLD,
            model_version=MOCK_VERSION,
            risk_level=risk,
            risk_drivers=drivers,
            stage_risk_mass=self._stage_shares(stage_results),
            explanation=self._explain(inp, stage_results) if include_explanation else None,
            caveats=caveats,
            constraint_override_applied=overridden,
            inference_backend=InferenceBackend.MOCK,
            is_mock=True,
            feature_schema_hash=FEATURE_SCHEMA_HASH,
            constraints_version=self.registry.version,
            compute_ms=round((time.perf_counter() - t0) * 1000, 3),
        )

    @staticmethod
    def _group(spec: Mapping[str, Any]) -> str:
        return {"c": "temperature", "bar": "pressure", "s": "time", "h": "time"}.get(
            str(spec.get("unit") or ""), "other"
        )

    def _explain(
        self, inp: ProcessInput, stage_results: Sequence[StageResult], top_k: int = 10
    ) -> LocalExplanation:
        self._require_complete(stage_results)
        flat = inp.flat()
        rows: list[FeatureAttribution] = []
        for name, spec in self.registry.parameters.items():
            value = flat.get(name)
            if value is None:
                continue
            shap = round(_unit("shap", name, flat) - 0.5, 4)
            rows.append(
                FeatureAttribution(
                    feature=name,
                    display_name=str(spec.get("display_name", name)),
                    value=value,
                    shap_value=shap,
                    direction="toward_fail" if shap >= 0 else "toward_pass",
                    stage=str(spec.get("stage") or "CONTEXT"),
                    group=self._group(spec),
                )
            )
        rows.sort(key=lambda a: (-abs(a.shap_value), a.feature))
        top = rows[:top_k]
        groups: dict[str, float] = {}
        for a in top:
            groups[a.group] = groups.get(a.group, 0.0) + a.shap_value
        return LocalExplanation(
            base_value=0.0,
            attributions=top,
            grouped_attributions=[
                GroupedAttribution(group=g, shap_sum=round(v, 4)) for g, v in sorted(groups.items())
            ],
            stage_risk_mass=self._stage_shares(stage_results),
            background_version=MOCK_VERSION,
            show_caveat_banner=any(r.anomaly.flag for r in stage_results),
        )

    def explain(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
    ) -> LocalExplanation:
        return self._explain(inp, stage_results)

    def global_explanation(self) -> GlobalExplanation:
        return GlobalExplanation(
            model_version=MOCK_VERSION,
            mean_abs_shap=[
                GlobalAttributionItem(
                    feature=name,
                    value=round(_unit("global", name), 4),
                    stage=str(spec.get("stage") or "CONTEXT"),
                )
                for name, spec in self.registry.parameters.items()
            ],
            computed_on="mock (no training data)",
            n_rows=0,
        )

    def evaluate(self, inp: ProcessInput, include_explanation: bool = False) -> PipelineResult:
        stages = self._run_all_stages(inp)
        return PipelineResult(
            stage_results=stages,
            prediction=self.predict(inp, stages, include_explanation=include_explanation),
        )

    # ------------------------------------------------------------------ decision support
    def _settings(self) -> dict[str, Any]:
        return dict(self.registry.recommendation_cfg)

    def _with_recipe(self, inp: ProcessInput, updates: Mapping[str, float]) -> ProcessInput:
        recipe = inp.recipe.model_dump()
        old = dict(recipe)
        recipe.update(updates)
        if self._settings().get("cycle_time_follows_stage_times", False):
            recipe["cycle_time_s"] = old["cycle_time_s"] + sum(
                recipe[k] - old[k] for k in _CYCLE_FOLLOWS
            )
        return ProcessInput.model_validate({"context": inp.context.model_dump(), "recipe": recipe})

    def _guard(self, candidate: ProcessInput) -> tuple[GuardName | None, list[GuardCheck]]:
        """Registry checks a candidate must pass. Returns the first failing check, if any."""
        out: list[GuardCheck] = []
        recipe = candidate.recipe.model_dump()
        if not all(self.registry.check_box(k, float(v))[0] for k, v in recipe.items()):
            return "box", out
        out.append(GuardCheck(check="box", passed=True, detail="registry box check passed"))
        if self.registry.check_couplings(candidate.recipe, candidate.context):
            return "couplings", out
        out.append(GuardCheck(check="couplings", passed=True, detail="registry couplings passed"))
        return None, out

    def _step_toward_nominal(self, name: str, value: float) -> float:
        spec = self._spec(name)
        step, lo, hi = float(spec["step"]), float(spec["min"]), float(spec["max"])
        nominal = _numeric(spec.get("nominal"))
        nominal = value if nominal is None else nominal
        if value < nominal:
            target = value + step
        elif value > nominal:
            target = value - step
        else:
            target = value + step if value + step <= hi else value - step
        return round(min(hi, max(lo, target)), 6)

    def recommend(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        t0 = time.perf_counter()
        self._require_complete(stage_results)
        locked = set(request.locked)
        unknown = [n for n in locked if self.registry.get_parameter(n) is None]
        if unknown:
            raise InvalidInputError(f"unknown locked parameters {unknown}", field="locked")
        recipe = inp.recipe.model_dump()
        knobs = sorted(
            (
                name
                for name, spec in self.registry.parameters.items()
                if spec.get("kind") == "setpoint"
                and spec.get("actionable")
                and name not in locked
                and name in recipe
            ),
            key=lambda name: _unit("knob", name, recipe),
        )
        combos = [
            knobs[offset : offset + k]
            for k in range(1, request.max_changes + 1)
            for offset in range(len(knobs))
            if offset + k <= len(knobs)
        ]
        pool: list[dict[str, Any]] = []
        rejected: dict[str, int] = {}
        evaluated = 0
        for combo in combos:
            if time.perf_counter() - t0 > request.time_budget_s:
                break
            updates = {n: self._step_toward_nominal(n, float(recipe[n])) for n in combo}
            updates = {k: v for k, v in updates.items() if v != recipe[k]}
            if not updates:
                continue
            candidate = self._with_recipe(inp, updates)
            evaluated += 1
            failed, guards = self._guard(candidate)
            if failed is None:
                result = self.evaluate(candidate)
                if any(
                    b.severity is ConstraintSeverity.CRITICAL
                    for r in result.stage_results
                    for b in r.constraint_breaches
                ):
                    failed = "hard_constraints"
            if failed is not None:
                rejected[failed] = rejected.get(failed, 0) + 1
                continue
            guards.append(
                GuardCheck(check="hard_constraints", passed=True, detail="no critical breach")
            )
            if result.prediction.p_fail >= prediction.p_fail:
                continue  # no improvement: never offered
            pool.append(
                {"updates": updates, "input": candidate, "result": result, "guards": guards}
            )

        chosen = self._choose(pool, request.n_options)
        candidates = [
            self._candidate(inp, prediction, c, label, request.seed) for c, label in chosen
        ]
        candidates.sort(key=lambda c: -c.score)
        candidates = [c.model_copy(update={"option_rank": i}) for i, c in enumerate(candidates, 1)]
        return RecommendationResponse(
            base_p_fail=prediction.p_fail,
            base_label=prediction.label,
            candidates=candidates,
            evaluated_count=evaluated,
            rejected_counts=rejected,
            empty_reason=None
            if candidates
            else "MOCK: no placeholder candidate lowered p_fail within the registry constraints",
            model_version=MOCK_VERSION,
            constraints_version=self.registry.version,
            compute_ms=round((time.perf_counter() - t0) * 1000, 3),
        )

    @staticmethod
    def _choose(
        pool: list[dict[str, Any]], n_options: int
    ) -> list[tuple[dict[str, Any], OptionLabel]]:
        """Minimal = fewest changes, Aggressive = lowest p_fail, Balanced = best of the rest."""
        remaining = list(pool)
        picks: list[tuple[dict[str, Any], OptionLabel]] = []

        def take(key: Any, label: OptionLabel) -> None:
            if remaining and len(picks) < n_options:
                best = min(remaining, key=key)
                remaining.remove(best)
                picks.append((best, label))

        take(lambda c: c["result"].prediction.p_fail, _OPTION_LABELS[2])
        take(lambda c: (len(c["updates"]), c["result"].prediction.p_fail), _OPTION_LABELS[0])
        take(lambda c: c["result"].prediction.p_fail + 0.05 * len(c["updates"]), _OPTION_LABELS[1])
        return picks

    def _candidate(
        self,
        base: ProcessInput,
        prediction: PredictionResult,
        c: dict[str, Any],
        label: OptionLabel,
        seed: int,
    ) -> RecommendationCandidate:
        settings = self._settings()
        trials = int(settings.get("stability_trials", 20))
        noise = float(settings.get("stability_noise_fraction_of_step", 0.5))
        max_flip_rate = float(settings.get("max_unstable_flip_rate", 0.2))
        weights: dict[str, float] = dict(settings.get("weights", {}))
        result: PipelineResult = c["result"]
        new_p = result.prediction.p_fail
        old_recipe, new_recipe = base.recipe.model_dump(), c["input"].recipe.model_dump()
        changes = [
            ParameterChange(
                parameter=name,
                from_value=old_recipe[name],
                to_value=value,
                delta=round(value - old_recipe[name], 6),
                unit=str(self._spec(name).get("unit") or ""),
            )
            for name, value in c["updates"].items()
        ]
        flips = 0
        for trial in range(trials):
            noisy = {}
            for name, value in c["updates"].items():
                step = float(self._spec(name).get("step") or 0.0)
                jitter = (2 * _unit("stability", seed, trial, name) - 1) * step
                noisy[name] = value + jitter * noise
            trial_label = self.evaluate(self._with_recipe(base, noisy)).prediction.label
            flips += int(trial_label is not result.prediction.label)
        stable = trials == 0 or flips / trials <= max_flip_rate
        cycle_delta = new_recipe["cycle_time_s"] - old_recipe["cycle_time_s"]
        cycle_pct = 100.0 * cycle_delta / old_recipe["cycle_time_s"]
        cost = sum(float(self._spec(ch.parameter).get("change_cost") or 0.0) for ch in changes)
        score = (
            weights.get("w1_improvement", 1.0) * (prediction.p_fail - new_p)
            - weights.get("w2_change_cost", 0.0) * cost
            - weights.get("w3_instability", 0.0) * (flips / trials if trials else 0.0)
            - weights.get("w5_cycle_time", 0.0) * abs(cycle_pct) / 100.0
        )
        return RecommendationCandidate(
            option_rank=1,
            option_label=label,
            changes=changes,
            predicted_p_fail=new_p,
            predicted_label=result.prediction.label,
            delta_p_fail=round(new_p - prediction.p_fail, 6),
            stage_health_after=[
                StageHealthAfter(
                    stage=r.stage_name, health_score=r.health_score, risk_level=r.risk_level
                )
                for r in result.stage_results
            ],
            guard_checks=[
                *c["guards"],
                GuardCheck(check="step_size", passed=True, detail="one registry step per change"),
                GuardCheck(
                    check="stability",
                    passed=stable,
                    detail=f"{flips}/{trials} label flips under step noise",
                ),
            ],
            stability=StabilityReport(trials=trials, flips=flips, stable=stable),
            in_distribution=True,  # the mock has no training distribution to compare against
            flags=[] if stable else [CandidateFlag.UNSTABLE],
            cycle_time_delta_s=round(cycle_delta, 6),
            cycle_time_delta_pct=round(cycle_pct, 4),
            change_cost=round(cost, 6),
            score=round(score, 6),
            rationale=[MOCK_NOTE],
            search_method="coordinate",
        )

    def sensitivity(self, inp: ProcessInput, parameter: str, steps: int = 40) -> SensitivityResult:
        spec = self._spec(parameter)
        if not spec.get("actionable"):
            raise LockedParameterError(f"{parameter} is not actionable", field=parameter)
        if steps < 2:
            raise InvalidInputError("steps must be at least 2", field="steps")
        lo, hi = float(spec["min"]), float(spec["max"])
        current = float(inp.recipe.model_dump()[parameter])

        def p_at(value: float) -> tuple[float, PredictionLabel]:
            pred = self.evaluate(self._with_recipe(inp, {parameter: value})).prediction
            return pred.p_fail, pred.label

        span = hi - lo
        values = [round(lo + span * i / (steps - 1), 6) for i in range(steps)]
        points = [
            SensitivityPoint(value=v, p_fail=p, label=lbl) for v in values for p, lbl in [p_at(v)]
        ]
        h = float(spec.get("step") or span / (steps - 1))
        a, b = max(lo, current - h), min(hi, current + h)
        gradient = (p_at(b)[0] - p_at(a)[0]) / (b - a) if b > a else 0.0
        current_label = p_at(current)[1]
        flips = [pt.value for pt in points if pt.label is not current_label]
        p_values = [pt.p_fail for pt in points]
        return SensitivityResult(
            parameter=parameter,
            unit=str(spec.get("unit") or ""),
            current_value=current,
            points=points,
            local_gradient=round(gradient, 6),
            range_swing=round(max(p_values) - min(p_values), 6),
            flip_point=min(flips, key=lambda v: abs(v - current)) if flips else None,
        )
