from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.db.models import Machine, MaterialLot, Product
from app.db.session import ALEMBIC_INI, Database
from app.db.vocab import RECIPE_FIELDS

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["db_url"] = url
    cfg.attributes["configure_logger"] = False
    return cfg


def migrate(url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(url), revision)


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def database(db_url: str) -> Iterator[Database]:
    migrate(db_url)
    db = Database(db_url)
    yield db
    db.dispose()


@pytest.fixture
def session(database: Database) -> Iterator[Session]:
    s = database.session_factory()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


@pytest.fixture
def refs(session: Session) -> tuple[Machine, Product, MaterialLot]:
    machine = Machine(
        code="MC-03",
        machine_type="ELECTRIC",
        tonnage_ton=180,
        max_inj_pressure_bar=2000,
        max_clamp_force_ton=180,
        installed_on=date(2020, 1, 1),
        last_maintenance_on=date(2026, 9, 1),
    )
    product = Product(
        code="PP-JBOX-42",
        name="PP junction-box housing",
        cavity_count=4,
        nominal_shot_weight_g=42,
        wall_thickness_mm=2.5,
        projected_area_cm2=100,
    )
    lot = MaterialLot(
        lot_code="A-771",
        resin_grade="PP-H",
        mfi=12,
        moisture_pct=0.04,
        regrind_pct=15,
        colourant_pct=2,
    )
    session.add_all([machine, product, lot])
    session.flush()
    return machine, product, lot


@pytest.fixture
def recipe() -> dict[str, float]:
    # Arbitrary in-range numbers; the DB layer does not validate domain windows.
    return {name: float(i + 1) for i, name in enumerate(RECIPE_FIELDS)}
