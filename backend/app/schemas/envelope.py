"""Response envelope shared by every JSON endpoint (roadmap 9.3.1, Plan 16.3).

``{"data": ..., "error": ..., "meta": {"request_id", "latency_ms", "api_version", ...}}``
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

API_VERSION = "1"


class ErrorDetail(BaseModel):
    """One per-field problem in a 422 response."""

    model_config = ConfigDict(extra="forbid")

    field: str | None = None
    code: str
    message: str
    limit: float | str | None = None
    value: Any = None


class ErrorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field: str | None = None
    details: list[ErrorDetail] | None = None
    constraint_version: str | None = None
    hint: str | None = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    latency_ms: float | None = None
    api_version: str = API_VERSION
    # Version of app.contracts; null until Role 1 contracts are integrated (roadmap M1).
    contracts_version: str | None = None
    total: int | None = Field(default=None, description="Total rows for paginated lists")


class Envelope[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: T | None = None
    error: ErrorBody | None = None
    meta: Meta
