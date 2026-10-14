"""Idempotent seed of reference data from ``fleet.yaml`` (roadmap 8.1, R2-P2 task 6).

``fleet.yaml`` is authored by Role 1 (``backend/app/domain/fleet.yaml``). Expected structure, using
the canonical contract field names of roadmap 7.3-7.5:

    fleet_version: fleet-0.1.0
    machines:
      - {machine_id: MC-03, machine_type: ELECTRIC, tonnage_ton: 180, max_inj_pressure_bar: 2000,
         max_clamp_force_ton: 180, installed_on: 2019-04-01, last_maintenance_on: 2026-08-20}
    products:
      - {product_id: PP-JBOX-42, name: "PP junction-box housing", cavity_count: 4,
         nominal_shot_weight_g: 42, wall_thickness_mm: 2.5, projected_area_cm2: 100}
    material_lots:
      - {material_lot_id: A-771, resin_grade: PP-H, mfi: 12, moisture_pct: 0.04,
         regrind_pct: 15, colourant_pct: 2, received_on: 2026-09-01}

Every entry is imported unless it sets ``demo: false``. Existing codes are left untouched
(runs snapshot reference values, so history never depends on later edits). The mock model-version
row is always ensured.

Usage:
    uv run python -m app.db.seed [--fleet PATH] [--database-url URL]
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Machine, MaterialLot, Product
from app.db.repositories import ModelVersionRepository


class _Entry(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    demo: bool = True


class FleetMachine(_Entry):
    machine_id: str = Field(min_length=1, max_length=32)
    machine_type: Literal["HYDRAULIC", "ELECTRIC", "HYBRID"]
    tonnage_ton: float = Field(gt=0)
    max_inj_pressure_bar: float = Field(gt=0)
    max_clamp_force_ton: float = Field(gt=0)
    installed_on: date
    last_maintenance_on: date


class FleetProduct(_Entry):
    product_id: str = Field(min_length=1, max_length=32)
    name: str
    cavity_count: int = Field(gt=0)
    nominal_shot_weight_g: float = Field(gt=0)
    wall_thickness_mm: float = Field(gt=0)
    projected_area_cm2: float = Field(gt=0)


class FleetLot(_Entry):
    material_lot_id: str = Field(min_length=1, max_length=32)
    resin_grade: str
    mfi: float = Field(gt=0)
    moisture_pct: float = Field(ge=0, le=100)
    regrind_pct: float = Field(ge=0, le=100)
    colourant_pct: float = Field(ge=0, le=100)
    received_on: date | None = None
    notes: str | None = None


class FleetFile(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)
    fleet_version: str
    machines: list[FleetMachine] = []
    products: list[FleetProduct] = []
    material_lots: list[FleetLot] = []


@dataclass
class SeedReport:
    fleet_version: str
    inserted: dict[str, list[str]] = field(
        default_factory=lambda: {"machines": [], "products": [], "material_lots": []}
    )
    unchanged: dict[str, list[str]] = field(
        default_factory=lambda: {"machines": [], "products": [], "material_lots": []}
    )

    def summary(self) -> str:
        parts = [
            f"{k}: +{len(self.inserted[k])} new, {len(self.unchanged[k])} existing"
            for k in self.inserted
        ]
        return f"fleet {self.fleet_version} -> " + "; ".join(parts)


class FleetFileError(ValueError):
    pass


def load_fleet(path: Path) -> FleetFile:
    if not path.is_file():
        raise FleetFileError(
            f"fleet file not found: {path}. It is delivered by Role 1 (R1-P1); "
            "see docs/coordination/ROLE1_AGENT_INSTRUCTIONS.md"
        )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return FleetFile.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise FleetFileError(f"invalid fleet file {path}: {exc}") from exc


def seed(session: Session, fleet: FleetFile) -> SeedReport:
    report = SeedReport(fleet_version=fleet.fleet_version)

    for m in (m for m in fleet.machines if m.demo):
        if session.scalar(select(Machine.id).where(Machine.code == m.machine_id)) is not None:
            report.unchanged["machines"].append(m.machine_id)
            continue
        session.add(
            Machine(
                code=m.machine_id,
                machine_type=m.machine_type,
                tonnage_ton=m.tonnage_ton,
                max_inj_pressure_bar=m.max_inj_pressure_bar,
                max_clamp_force_ton=m.max_clamp_force_ton,
                installed_on=m.installed_on,
                last_maintenance_on=m.last_maintenance_on,
                fleet_version=fleet.fleet_version,
            )
        )
        report.inserted["machines"].append(m.machine_id)

    for p in (p for p in fleet.products if p.demo):
        if session.scalar(select(Product.id).where(Product.code == p.product_id)) is not None:
            report.unchanged["products"].append(p.product_id)
            continue
        session.add(
            Product(
                code=p.product_id,
                name=p.name,
                cavity_count=p.cavity_count,
                nominal_shot_weight_g=p.nominal_shot_weight_g,
                wall_thickness_mm=p.wall_thickness_mm,
                projected_area_cm2=p.projected_area_cm2,
                fleet_version=fleet.fleet_version,
            )
        )
        report.inserted["products"].append(p.product_id)

    for lot in (lot for lot in fleet.material_lots if lot.demo):
        exists = session.scalar(
            select(MaterialLot.id).where(MaterialLot.lot_code == lot.material_lot_id)
        )
        if exists is not None:
            report.unchanged["material_lots"].append(lot.material_lot_id)
            continue
        session.add(
            MaterialLot(
                lot_code=lot.material_lot_id,
                resin_grade=lot.resin_grade,
                mfi=lot.mfi,
                moisture_pct=lot.moisture_pct,
                regrind_pct=lot.regrind_pct,
                colourant_pct=lot.colourant_pct,
                received_on=lot.received_on,
                notes=lot.notes,
                fleet_version=fleet.fleet_version,
            )
        )
        report.inserted["material_lots"].append(lot.material_lot_id)

    ModelVersionRepository(session).ensure_mock()
    session.flush()
    return report


def main(argv: list[str] | None = None) -> int:
    from app.core.config import get_settings
    from app.db.session import Database

    settings = get_settings()
    parser = argparse.ArgumentParser(description="Seed reference data from fleet.yaml")
    parser.add_argument("--fleet", type=Path, default=settings.fleet_path)
    parser.add_argument("--database-url", default=settings.database_url)
    args = parser.parse_args(argv)

    try:
        fleet = load_fleet(args.fleet)
    except FleetFileError as exc:
        print(f"seed: {exc}", file=sys.stderr)
        return 2

    db = Database(args.database_url)
    status = db.status()
    if not status.migrated:
        print(f"seed: database not ready ({status.detail})", file=sys.stderr)
        return 3
    with db.session() as session:
        report = seed(session, fleet)
    db.dispose()
    print(f"seed: {report.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
