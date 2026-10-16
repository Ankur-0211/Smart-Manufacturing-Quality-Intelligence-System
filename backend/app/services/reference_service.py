"""Reference data: machines, products, material lots (roadmap R2-P3 task 3)."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from app.db.base import utcnow
from app.db.models import Machine, MaterialLot
from app.db.repositories import (
    ReferenceRepository,
    lot_snapshot,
    machine_snapshot,
    product_snapshot,
)
from app.db.session import Database


def machine_json(m: Machine, today: date) -> dict[str, Any]:
    return {
        **machine_snapshot(m, today=today),
        "installed_on": m.installed_on,
        "last_maintenance_on": m.last_maintenance_on,
    }


def lot_json(lot: MaterialLot) -> dict[str, Any]:
    return {**lot_snapshot(lot), "received_on": lot.received_on, "notes": lot.notes}


class ReferenceService:
    def __init__(self, db: Database) -> None:
        self.db = db

    def machines(self, today: date | None = None) -> list[dict[str, Any]]:
        today = today or utcnow().date()
        with self.db.session() as s:
            return [machine_json(m, today) for m in ReferenceRepository(s).list_machines()]

    def products(self) -> list[dict[str, Any]]:
        with self.db.session() as s:
            return [product_snapshot(p) for p in ReferenceRepository(s).list_products()]

    def materials(self) -> list[dict[str, Any]]:
        with self.db.session() as s:
            return [lot_json(lot) for lot in ReferenceRepository(s).list_materials()]

    def create_material(
        self,
        payload: Mapping[str, Any],
        *,
        validate_attributes: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create a lot after ``validate_attributes`` (the registry box check) accepts it.

        Raises ``DuplicateError`` when the lot code exists.
        """
        attributes = {
            k: payload[k]
            for k in ("resin_grade", "mfi", "moisture_pct", "regrind_pct", "colourant_pct")
        }
        values = validate_attributes(attributes)
        with self.db.session() as s:
            lot = ReferenceRepository(s).create_material(
                lot_code=payload["material_lot_id"],
                received_on=payload.get("received_on"),
                notes=payload.get("notes"),
                **values,
            )
            s.flush()
            return lot_json(lot)
