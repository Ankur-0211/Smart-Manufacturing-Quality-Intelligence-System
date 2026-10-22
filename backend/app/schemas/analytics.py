"""``/analytics/*`` payloads (roadmap 9.3.2, R2-P8). Every number is a stored-data aggregation."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class AnalyticsFiltersOut(BaseModel):
    """The exclusions and range that produced the numbers (stated on screen, Plan §13.7)."""

    include_whatif: bool
    include_mock: bool
    include_unfinished: bool
    created_from: datetime | None
    created_to: datetime | None


class Outcome(BaseModel):
    runs: int
    with_prediction: int
    predicted_fail: int
    # model-predicted FAIL share among runs with a prediction; null when none has one
    predicted_fail_rate: float | None
    mean_p_fail: float | None


class StageRiskFrequency(BaseModel):
    stage: str
    counts: dict[str, int]  # risk level -> number of stage results
    total: int


class DayOutcome(Outcome):
    day: date


class AnalyticsSummary(Outcome):
    filters: AnalyticsFiltersOut
    excluded: dict[str, int]  # active exclusion -> runs it removed
    risk_levels: dict[str, int]
    not_releasable: int
    stage_risk_frequency: list[StageRiskFrequency]
    runs_over_time: list[DayOutcome]


class GroupOutcome(Outcome):
    key: str


class GroupedAnalytics(BaseModel):
    filters: AnalyticsFiltersOut
    rows: list[GroupOutcome]


class MaterialAnalytics(GroupedAnalytics):
    group: str


class BucketOutcome(Outcome):
    lo: float
    hi: float


class ParameterWindow(BaseModel):
    min: float
    max: float


class ParameterAnalytics(BaseModel):
    filters: AnalyticsFiltersOut
    parameter: str
    unit: str | None
    window: ParameterWindow
    rows: list[BucketOutcome]


class SpcPoint(BaseModel):
    run_id: str
    created_at: datetime
    value: float


class SpcStatus(BaseModel):
    available: bool
    reason: str | None


class SpcOut(BaseModel):
    """The stored series, and SPC alerts only when the intelligence layer provides them
    (Role 2 never implements SPC rules, roadmap R2-P8 §15)."""

    machine_id: str
    parameter: str
    unit: str | None
    filters: AnalyticsFiltersOut
    series: list[SpcPoint]
    spc: SpcStatus
    alerts: list[dict[str, object]] | None
