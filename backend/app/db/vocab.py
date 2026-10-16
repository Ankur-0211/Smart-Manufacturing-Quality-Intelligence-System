"""Canonical vocabularies persisted by the DB layer (roadmap 7.2, 7.6).

Derived from ``app.contracts`` (Role 1); the DB layer never hand-writes these values. Migration
0001 freezes them into CHECK constraints, so a contract change that alters any of them needs a new
migration: ``backend/tests/db/test_vocab_matches_contracts.py`` fails until one exists.
"""

from __future__ import annotations

from typing import Final

from app.contracts.enums import (
    INTELLIGENCE_STAGES,
    InferenceBackend,
    MachineType,
    PredictionLabel,
    RiskLevel,
    RunMode,
    RunStatus,
    SpeedFactor,
    StageSubstate,
)
from app.contracts.recipe import RECIPE_FIELDS as _CONTRACT_RECIPE_FIELDS

# Run status / FSM states
RUN_STATUSES: Final = tuple(s.value for s in RunStatus)
TERMINAL_STATUSES: Final = frozenset({RunStatus.FINAL_RESULT.value, RunStatus.ABORTED.value})

# Stages S1-S5 persisted in stage_results (QUALITY_INSPECTION lives in predictions)
STAGE_NAMES: Final = tuple(s.value for s in INTELLIGENCE_STAGES)
STAGE_SUBSTATES: Final = tuple(s.value for s in StageSubstate)
RISK_LEVELS: Final = tuple(r.value for r in RiskLevel)
PREDICTION_LABELS: Final = tuple(lbl.value for lbl in PredictionLabel)
RUN_MODES: Final = tuple(m.value for m in RunMode)
SPEED_FACTORS: Final = tuple(s.value for s in SpeedFactor)
INFERENCE_BACKENDS: Final = tuple(b.value for b in InferenceBackend)
MACHINE_TYPES: Final = tuple(t.value for t in MachineType)
# Model registry names are an R2 persistence concern (roadmap 9.4), not a contract enum.
MODEL_NAMES: Final = ("fusion", "anomaly", "stage_stats", "mock")

# ProcessRecipe setpoints, in contract order. One typed column each in run_parameters.
RECIPE_FIELDS: Final = _CONTRACT_RECIPE_FIELDS


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """CHECK constraint body restricting ``column`` to ``values``."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
