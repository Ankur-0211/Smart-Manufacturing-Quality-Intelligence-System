"""Orchestrator test fixtures: migrated temp DB, a seeded run, a recording fake executor."""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.contracts.enums import StageName
from app.db.models import Machine, MaterialLot, Product
from app.db.repositories import RunRepository
from app.db.session import Database
from app.db.vocab import RECIPE_FIELDS, STAGE_NAMES
from app.domain.constraint_loader import load_constraint_registry
from app.engine.cache import StageCache
from app.engine.events import EventBus
from app.services.simulation_service import SimulationService
from tests.db.conftest import migrate

_REGISTRY = load_constraint_registry()
STAGE_INPUTS: dict[str, list[str]] = {
    stage: _REGISTRY.stage_inputs(StageName(stage)) for stage in STAGE_NAMES
}
UPSTREAM_KEYS = {
    "MATERIAL_CONDITIONING": {"viscosity_class": "NOMINAL", "moisture_flag": False},
    "PLASTICIZING": {"effective_melt_temp_c": 232.5, "viscosity_proxy": 1.0},
    "INJECTION": {"fill_completion_proxy": 1.0, "cavity_pressure_estimate_bar": 400.0},
    "PACKING": {"residual_stress_proxy": 0.3},
    "COOLING": {},
}


class FakeExecutor:
    """TEST DOUBLE of the StageExecutor port. Produces contract-shaped JSON (roadmap §7.9/§7.12);
    numbers are arbitrary and carry no domain meaning."""

    inference_backend = "mock"
    constraints_version = "constraints-0.1.0"

    def __init__(self) -> None:
        self.block: set[str] = set()
        self.anomaly: set[str] = set()
        self.fail_on: str | None = None
        self.stage_calls: list[tuple[str, dict[str, Any]]] = []
        self.predict_calls: list[list[Mapping[str, Any]]] = []

    def module_version(self, stage: str) -> str:
        return f"{stage.lower()}-test"

    def stage_inputs(self, stage: str) -> Sequence[str]:
        return STAGE_INPUTS[stage]

    def run_stage(
        self, stage: str, process_input: Mapping[str, Any], upstream: Mapping[str, Any]
    ) -> dict[str, Any]:
        if self.fail_on == stage:
            raise RuntimeError(f"boom in {stage}")
        self.stage_calls.append((stage, dict(upstream)))
        index = STAGE_NAMES.index(stage) + 1
        out = dict(upstream)
        out.update(UPSTREAM_KEYS[stage])
        blocked = stage in self.block
        breaches = (
            [
                {
                    "rule_id": "HC-TEST",
                    "severity": "CRITICAL",
                    "parameters": [],
                    "value": None,
                    "limit": None,
                    "message": "test breach",
                    "hint": None,
                    "provenance": "heuristic",
                    "constraints_version": "constraints-0.1.0",
                }
            ]
            if blocked
            else []
        )
        return {
            "stage_name": stage,
            "sequence_index": index,
            "substate": "BLOCKED" if blocked else "COMPLETED",
            "inputs_used": {k: None for k in STAGE_INPUTS[stage][:2]},
            "upstream_in": dict(upstream),
            "upstream_out": out,
            "health_score": 0.2 if blocked else 0.9,
            "risk_level": "CRITICAL" if blocked else "NORMAL",
            "risk_ordinal": 4 if blocked else 0,
            "anomaly": {
                "flag": stage in self.anomaly,
                "score": 0.9 if stage in self.anomaly else 0.1,
                "method": "zscore",
                "contributors": [],
            },
            "indicators": {"test_indicator": float(index)},
            "indicator_provenance": {"test_indicator": "heuristic"},
            "notes": [],
            "constraint_breaches": breaches,
            "blocked": blocked,
            "block_reason": "test critical breach" if blocked else None,
            "module_version": self.module_version(stage),
            "constraints_version": self.constraints_version,
        }

    def predict(
        self, process_input: Mapping[str, Any], stage_results: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        if self.fail_on == "QUALITY_INSPECTION":
            raise RuntimeError("boom in predict")
        self.predict_calls.append([copy.deepcopy(dict(r)) for r in stage_results])
        overridden = any(r.get("overridden") for r in stage_results)
        return {
            "label": "FAIL",
            "p_fail": 0.71,
            "p_fail_raw": 0.64,
            "threshold_used": 0.42,
            "model_version": "mock-0.0.0",
            "risk_level": "CRITICAL" if overridden else "HIGH",
            "risk_drivers": [{"source": "model", "detail": "test", "weight": 1.0}],
            "stage_risk_mass": [{"stage": "COOLING", "share": 1.0}],
            "explanation": None,
            "uncertainty": {"method": "none", "value": None},
            "anomaly_global": None,
            "ood": {"is_out_of_distribution": False, "features_outside": []},
            "caveats": [{"code": "MOCK_INFERENCE", "message": "test", "features": []}],
            "constraint_override_applied": overridden,
            "inference_backend": "mock",
            "is_mock": True,
            "feature_schema_hash": None,
            "constraints_version": self.constraints_version,
        }


@pytest.fixture
def database(tmp_path: Path) -> Iterator[Database]:
    url = f"sqlite:///{(tmp_path / 'sim.db').as_posix()}"
    migrate(url)
    db = Database(url)
    yield db
    db.dispose()


def create_test_run(
    database: Database,
    *,
    recipe: Mapping[str, float] | None = None,
    lot_code: str = "A-771",
    moisture_pct: float = 0.04,
    **kw: Any,
) -> str:
    """Create machine/product/lot (once) and a run. Without ``recipe`` the setpoints are
    arbitrary in-type numbers; pass a real recipe when an actual intelligence evaluates it."""
    with database.session() as s:
        machine = s.query(Machine).filter_by(code="MC-03").one_or_none() or Machine(
            code="MC-03",
            machine_type="ELECTRIC",
            tonnage_ton=180,
            max_inj_pressure_bar=2000,
            max_clamp_force_ton=180,
            installed_on=date(2020, 1, 1),
            last_maintenance_on=date(2026, 9, 1),
        )
        product = s.query(Product).filter_by(code="PP-JBOX-42").one_or_none() or Product(
            code="PP-JBOX-42",
            name="housing",
            cavity_count=1,
            nominal_shot_weight_g=42,
            wall_thickness_mm=2.2,
            projected_area_cm2=125,
        )
        lot = s.query(MaterialLot).filter_by(lot_code=lot_code).one_or_none() or MaterialLot(
            lot_code=lot_code,
            resin_grade="PP-H",
            mfi=12,
            moisture_pct=moisture_pct,
            regrind_pct=15,
            colourant_pct=2,
        )
        s.add_all([machine, product, lot])
        s.flush()
        run = RunRepository(s).create(
            machine=machine,
            product=product,
            material_lot=lot,
            parameters=dict(recipe)
            if recipe is not None
            else {f: float(i + 1) for i, f in enumerate(RECIPE_FIELDS)},
            today=date(2026, 10, 15),
            **kw,
        )
        return run.id


@pytest.fixture
def make_run(database: Database) -> Callable[..., str]:
    return lambda **kw: create_test_run(database, **kw)


@pytest.fixture
def executor() -> FakeExecutor:
    return FakeExecutor()


@pytest.fixture
def service(database: Database, executor: FakeExecutor) -> SimulationService:
    return SimulationService(
        database, EventBus(), StageCache(100), executor=executor, stage_presentation_ms=0
    )
