"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

Shared base and field types for the contract models added in the bootstrap (roadmap 7.1).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    """Frozen, closed, JSON-safe (no NaN/Infinity in any payload, roadmap 7.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


Probability = Annotated[float, Field(ge=0.0, le=1.0)]
Ordinal = Annotated[int, Field(ge=0, le=4)]
