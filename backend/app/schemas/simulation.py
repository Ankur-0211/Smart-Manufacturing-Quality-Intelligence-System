"""API schemas for the simulation endpoints (roadmap §9.3.2, §7.17).

PROVISIONAL TYPING: stage results and predictions are passed through as JSON objects
(``dict[str, Any]``) because their contract types (``StageResult``, ``PredictionResult``) are not
delivered yet. When ``app.contracts`` lands they become the contract models; field names already
follow roadmap §7.9/§7.12, so the JSON on the wire does not change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StageNameLiteral = Literal[
    "MATERIAL_CONDITIONING", "PLASTICIZING", "INJECTION", "PACKING", "COOLING"
]
SpeedLiteral = Literal["0.5x", "1x", "2x", "instant"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartRequest(_Strict):
    mode: Literal["auto", "stepwise"] = "auto"
    speed_factor: SpeedLiteral | None = None


class OverrideRequest(_Strict):
    stage: StageNameLiteral
    acknowledgement: str = Field(min_length=3, max_length=500)


class AbortRequest(_Strict):
    reason: str | None = Field(default=None, max_length=200)


class LabelRequest(_Strict):
    scenario_label: str | None = Field(default=None, max_length=200)


class EventOut(BaseModel):
    run_id: str
    seq: int
    ts: str
    type: str
    stage: str | None
    payload: dict[str, Any]


class SimulationStateOut(BaseModel):
    run_id: str
    status: str
    mode: str
    speed_factor: str
    halt_on_critical: bool
    blocked_stage: str | None
    current_stage: str | None
    override_count: int
    abort_reason: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    context: dict[str, Any]
    parameters: dict[str, float]
    stage_results: list[dict[str, Any]]
    prediction: dict[str, Any] | None
    timeline: list[EventOut]
    parent_run_id: str | None
    is_whatif: bool
    scenario_label: str | None
    inference_backend: str | None
    constraints_version: str | None
    last_seq: int


class ScenarioSummary(BaseModel):
    """History row (roadmap §7.16)."""

    run_id: str
    parent_run_id: str | None
    is_whatif: bool
    scenario_label: str | None
    status: str
    created_at: datetime
    machine_id: str
    product_id: str
    material_lot_id: str
    label: str | None
    p_fail: float | None
    risk_level: str | None
    model_version: str | None
    inference_backend: str | None
