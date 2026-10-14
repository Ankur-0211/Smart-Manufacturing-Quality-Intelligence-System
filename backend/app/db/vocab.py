"""Canonical vocabularies persisted by the DB layer (roadmap 7.2, 7.6).

TEMPORARY SOURCE: these lists are transcribed from the roadmap because ``app.contracts`` (Role 1)
has not been delivered yet. When it lands, these constants MUST be replaced by imports from
``app.contracts.enums``. ``backend/tests/db/test_vocab_matches_contracts.py`` enforces equality
from then on (it skips until contracts exist).
"""

from __future__ import annotations

from typing import Final

# Run status / FSM states (roadmap 7.2 RunStatus)
RUN_STATUSES: Final = (
    "INITIALIZED",
    "MATERIAL_CONDITIONING",
    "PLASTICIZING",
    "INJECTION",
    "PACKING",
    "COOLING",
    "QUALITY_INSPECTION",
    "FINAL_RESULT",
    "PAUSED",
    "BLOCKED",
    "ABORTED",
)
TERMINAL_STATUSES: Final = frozenset({"FINAL_RESULT", "ABORTED"})

# Stages S1-S5 persisted in stage_results (QUALITY_INSPECTION lives in predictions)
STAGE_NAMES: Final = ("MATERIAL_CONDITIONING", "PLASTICIZING", "INJECTION", "PACKING", "COOLING")
STAGE_SUBSTATES: Final = ("PENDING", "RUNNING", "COMPLETED", "BLOCKED")
RISK_LEVELS: Final = ("NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL")
PREDICTION_LABELS: Final = ("PASS", "FAIL")
RUN_MODES: Final = ("auto", "stepwise")
SPEED_FACTORS: Final = ("0.5x", "1x", "2x", "instant")
INFERENCE_BACKENDS: Final = ("real", "mock")
MACHINE_TYPES: Final = ("HYDRAULIC", "ELECTRIC", "HYBRID")
MODEL_NAMES: Final = ("fusion", "anomaly", "stage_stats", "mock")

# ProcessRecipe setpoints, in roadmap 7.6 order. One typed column each in run_parameters.
RECIPE_FIELDS: Final = (
    "drying_time_h",
    "dryer_temp_c",
    "barrel_temp_rear_c",
    "barrel_temp_mid_c",
    "barrel_temp_front_c",
    "nozzle_temp_c",
    "melt_temp_c",
    "screw_rpm",
    "back_pressure_bar",
    "residence_time_s",
    "inj_velocity_mm_s",
    "inj_pressure_bar",
    "fill_time_s",
    "shot_size_mm",
    "switchover_position_mm",
    "clamp_force_ton",
    "hold_pressure_bar",
    "hold_time_s",
    "cushion_mm",
    "mold_temp_c",
    "cooling_time_s",
    "cycle_time_s",
    "ejection_force_proxy",
)


def sql_in(column: str, values: tuple[str, ...]) -> str:
    """CHECK constraint body restricting ``column`` to ``values``."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
