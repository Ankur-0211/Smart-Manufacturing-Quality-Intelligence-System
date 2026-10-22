"""What-if branching with partial re-simulation (roadmap 7.16, R2-P5 tasks 6-8; Plan §13).

- Stages upstream of the earliest stage invalidated by the changed parameters (Role 1's
  ``dependency_graph.invalidated_stages``) are reused from the parent; the rest are recomputed
  through the same executor and stage cache as normal runs, so a partial re-simulation equals a
  fresh full run by construction. Fusion (``predict``) is always recomputed.
- Parent rows are never modified. A persisted what-if is a new child run
  (``is_whatif=true``, ``parent_run_id``) with the parent's frozen context snapshot.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.contracts.context import ProcessInput
from app.contracts.errors import UnknownParameterError
from app.contracts.interface import QualityIntelligence
from app.contracts.sensitivity import SensitivityResult
from app.contracts.stage import StageResult
from app.db.base import utcnow
from app.db.repositories import PredictionRepository, RunRepository, StageResultRepository
from app.db.vocab import RECIPE_FIELDS, STAGE_NAMES
from app.domain.dependency_graph import invalidated_stages
from app.engine.cache import stage_cache_key
from app.services.predictions import persist_prediction, prediction_row_to_json
from app.services.simulation_service import (
    SimulationService,
    flat_input,
    stage_row_to_json,
    stage_row_values,
)

#: (recipe, RunContext JSON snapshot) -> validated recipe; raises on violation.
ParameterValidator = Callable[[Mapping[str, float], Mapping[str, Any]], Mapping[str, float]]

CYCLE_FOLLOWS = ("fill_time_s", "hold_time_s", "cooling_time_s")  # UD-09 stage times
RISK_ORDER = ("NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL")
_STAGE_FIELDS = frozenset(StageResult.model_fields)
_HEALTH_EPS = 1e-9


class BaseNotFinalError(Exception):
    """The base run has no final result yet -> HTTP 409."""


@dataclass(frozen=True)
class _Base:
    run_id: str
    status: str
    snapshot: dict[str, Any]
    parameters: dict[str, float]
    stage_results: list[dict[str, Any]]
    prediction: dict[str, Any] | None


def contract_stage(result: Mapping[str, Any]) -> dict[str, Any]:
    """StageResult fields only (drops presentation/override bookkeeping of stored rows)."""
    return {k: v for k, v in result.items() if k in _STAGE_FIELDS}


# ---------------------------------------------------------------------------
# Diff (roadmap 7.16)
# ---------------------------------------------------------------------------


def _breach_counts(stage_results: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    severities = [
        b.get("severity") for r in stage_results for b in r.get("constraint_breaches") or []
    ]
    return severities.count("WARNING"), severities.count("CRITICAL")


def build_diff(
    params_from: Mapping[str, float],
    params_to: Mapping[str, float],
    stages_from: Sequence[Mapping[str, Any]],
    stages_to: Sequence[Mapping[str, Any]],
    prediction_from: Mapping[str, Any],
    prediction_to: Mapping[str, Any],
) -> dict[str, Any]:
    parameters = [
        {
            "name": k,
            "from": params_from[k],
            "to": params_to[k],
            "delta": params_to[k] - params_from[k],
        }
        for k in RECIPE_FIELDS
        if params_to[k] != params_from[k]
    ]
    stages = []
    for a, b in zip(stages_from, stages_to, strict=True):
        delta = float(b["health_score"]) - float(a["health_score"])
        change = (
            "unchanged" if abs(delta) <= _HEALTH_EPS else ("improved" if delta > 0 else "worsened")
        )
        stages.append(
            {
                "stage": a["stage_name"],
                "health_from": a["health_score"],
                "health_to": b["health_score"],
                "risk_from": a["risk_level"],
                "risk_to": b["risk_level"],
                "change": change,
            }
        )
    warnings_from, critical_from = _breach_counts(stages_from)
    warnings_to, critical_to = _breach_counts(stages_to)
    p_from, p_to = float(prediction_from["p_fail"]), float(prediction_to["p_fail"])
    cycle_from, cycle_to = params_from["cycle_time_s"], params_to["cycle_time_s"]
    return {
        "parameters": parameters,
        "stages": stages,
        "prediction": {
            "label_from": prediction_from["label"],
            "label_to": prediction_to["label"],
            "p_fail_from": p_from,
            "p_fail_to": p_to,
            "p_fail_delta": round(p_to - p_from, 6),
            "flipped": prediction_from["label"] != prediction_to["label"],
        },
        "operational_risk": {
            "from": prediction_from["risk_level"],
            "to": prediction_to["risk_level"],
            "band_delta": RISK_ORDER.index(prediction_to["risk_level"])
            - RISK_ORDER.index(prediction_from["risk_level"]),
        },
        "constraint_compliance": {
            "warnings_from": warnings_from,
            "warnings_to": warnings_to,
            "critical_from": critical_from,
            "critical_to": critical_to,
        },
        "cycle_time": {
            "from": cycle_from,
            "to": cycle_to,
            "delta_s": round(cycle_to - cycle_from, 6),
            "delta_pct": round(100.0 * (cycle_to - cycle_from) / cycle_from, 4)
            if cycle_from
            else 0.0,
        },
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class WhatIfService:
    def __init__(self, simulation: SimulationService, *, cycle_time_follows: bool = True) -> None:
        self.simulation = simulation
        self.cycle_time_follows = cycle_time_follows

    def _load(self, run_id: str, *, require_final: bool = True) -> _Base:
        with self.simulation.db.session() as s:
            run = RunRepository(s).get(run_id)
            prediction = PredictionRepository(s).for_run(run_id)
            base = _Base(
                run_id=run.id,
                status=run.status,
                snapshot=dict(run.context_snapshot),
                parameters=run.parameters.as_dict(),
                stage_results=[
                    stage_row_to_json(r) for r in StageResultRepository(s).for_run(run_id)
                ],
                prediction=prediction_row_to_json(prediction) if prediction is not None else None,
            )
        if require_final and (base.status != "FINAL_RESULT" or base.prediction is None):
            raise BaseNotFinalError(
                f"run {run_id} is {base.status}; what-if needs a run with a final result"
            )
        return base

    def _merged_parameters(
        self, base: _Base, overrides: Mapping[str, float], validate: ParameterValidator
    ) -> dict[str, float]:
        unknown = [k for k in overrides if k not in RECIPE_FIELDS]
        if unknown:
            raise UnknownParameterError(
                f"unknown parameter(s) {', '.join(sorted(unknown))}", field=sorted(unknown)[0]
            )
        params = {**base.parameters, **{k: float(v) for k, v in overrides.items()}}
        if self.cycle_time_follows and "cycle_time_s" not in overrides:
            # UD-09: the cycle time follows changed stage times unless set explicitly.
            delta = sum(params[k] - base.parameters[k] for k in CYCLE_FOLLOWS)
            if delta:
                params["cycle_time_s"] = round(base.parameters["cycle_time_s"] + delta, 6)
        return dict(validate(params, base.snapshot))

    def evaluate(
        self,
        base_run_id: str,
        overrides: Mapping[str, float],
        *,
        validate: ParameterValidator,
        persist: bool = True,
        label: str | None = None,
    ) -> dict[str, Any]:
        """Run a what-if on a finished run. Returns the ``WhatIfResult`` JSON (roadmap 7.16)."""
        executor = self.simulation.require_executor()
        cache = self.simulation.cache
        base = self._load(base_run_id)
        assert base.prediction is not None
        params = self._merged_parameters(base, overrides, validate)
        changed = [k for k in RECIPE_FIELDS if params[k] != base.parameters[k]]
        invalid = {s.value for s in invalidated_stages(changed)}
        earliest = next(
            (i for i, stage in enumerate(STAGE_NAMES) if stage in invalid), len(STAGE_NAMES)
        )
        # Parent stages are reusable only if the same model and limits produced them. Role 1's
        # version info has no per-stage module versions (CCR-004 #9), so the parent's model
        # version (also the stage cache's version key) and constraints version are compared.
        same_model = base.prediction.get("model_version") == executor.module_version(STAGE_NAMES[0])
        same_limits = all(
            base.stage_results[i].get("constraints_version") == executor.constraints_version
            for i in range(earliest)
        )
        if not (same_model and same_limits):
            earliest = 0

        process_input = {"context": base.snapshot, "recipe": params}
        flat = flat_input(process_input)
        t0 = time.perf_counter()
        results: list[dict[str, Any]] = []
        for i, stage in enumerate(STAGE_NAMES):
            if i < earliest:
                results.append(contract_stage(base.stage_results[i]))
                continue
            upstream = dict(results[-1].get("upstream_out") or {}) if results else {}
            key = stage_cache_key(
                stage, flat, upstream, executor.module_version(stage), executor.constraints_version
            )
            result = cache.get(key)
            if result is None:
                result = executor.run_stage(stage, process_input, upstream)
                cache.put(key, result)
            results.append(dict(result))
        prediction = executor.predict(process_input, results)
        compute_ms = round((time.perf_counter() - t0) * 1000, 3)

        child_id = None
        if persist:
            child_id = self._persist(
                base, params, results, prediction, earliest, label=label, compute_ms=compute_ms
            )
        return {
            "run_id": child_id,
            "parent_run_id": base.run_id,
            "recomputed_stages": list(STAGE_NAMES[earliest:]),
            "reused_stages": list(STAGE_NAMES[:earliest]),
            "stage_results": results,
            "prediction": prediction,
            "diff": build_diff(
                base.parameters,
                params,
                base.stage_results,
                results,
                base.prediction,
                prediction,
            ),
        }

    def _persist(
        self,
        base: _Base,
        params: Mapping[str, float],
        results: Sequence[Mapping[str, Any]],
        prediction: Mapping[str, Any],
        earliest: int,
        *,
        label: str | None,
        compute_ms: float,
    ) -> str:
        executor = self.simulation.require_executor()
        with self.simulation.db.session() as s:
            runs = RunRepository(s)
            parent = runs.get(base.run_id)
            child = runs.create(
                machine=parent.machine,
                product=parent.product,
                material_lot=parent.material_lot,
                parameters=params,
                mode=parent.mode,
                speed_factor=parent.speed_factor,
                halt_on_critical=parent.halt_on_critical,
                scenario_label=label,
                parent_run_id=parent.id,
                inference_backend=executor.inference_backend,
                constraints_version=executor.constraints_version,
                snapshot=parent.context_snapshot,
            )
            stage_rows = StageResultRepository(s)
            parent_rows = list(stage_rows.for_run(parent.id))
            for i, result in enumerate(results):
                if i < earliest:
                    stage_rows.copy_for_child(parent_rows[i], child)
                else:
                    stage_rows.add(
                        child,
                        **stage_row_values(
                            result, presentation_ms=0.0, overridden=bool(result.get("blocked"))
                        ),
                    )
            persist_prediction(s, child, prediction, compute_ms=compute_ms)
            runs.set_status(child, "FINAL_RESULT", started_at=utcnow(), current_stage=None)
            return child.id

    def compare(self, run_id_a: str, run_id_b: str) -> dict[str, Any]:
        """Structured diff between two finished runs (``POST /whatif/compare``, P1)."""
        a, b = self._load(run_id_a), self._load(run_id_b)
        assert a.prediction is not None and b.prediction is not None
        return build_diff(
            a.parameters, b.parameters, a.stage_results, b.stage_results, a.prediction, b.prediction
        )

    def sensitivity(
        self, base_run_id: str, parameter: str, steps: int, intelligence: QualityIntelligence
    ) -> SensitivityResult:
        """1-D sweep around a finished run (``POST /whatif/sensitivity``, P1)."""
        base = self._load(base_run_id)
        inp = ProcessInput.model_validate({"context": base.snapshot, "recipe": base.parameters})
        return intelligence.sensitivity(inp, parameter, steps)
