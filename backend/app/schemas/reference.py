"""Reference payloads (roadmap 9.3.2): the contract models plus DB-only bookkeeping fields.

Contract fields are inherited, never re-declared (R2-P3 task 1). Limits are not declared here
either: lot attributes are box-checked against the registry by the service (rule B6).
"""

from __future__ import annotations

from datetime import date

from pydantic import Field

from app.contracts.context import MachineProfile, MaterialLot, ProductContext

CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$"


class MachineOut(MachineProfile):
    """``machine_age_days`` / ``days_since_maintenance`` are computed for today's date."""

    installed_on: date
    last_maintenance_on: date


class ProductOut(ProductContext):
    pass


class MaterialLotOut(MaterialLot):
    received_on: date | None = None
    notes: str | None = None


class MaterialLotCreate(MaterialLot):
    """``POST /materials`` body. The code format and registry windows are checked on create."""

    received_on: date | None = None
    notes: str | None = Field(default=None, max_length=500)
