from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Machine, MaterialLot, ModelVersion, Product
from app.db.seed import FleetFileError, load_fleet, main, seed
from app.db.session import Database
from tests.db.conftest import FIXTURES

FLEET = FIXTURES / "fleet_demo.yaml"


def _counts(session: Session) -> tuple[int, int, int, int]:
    return tuple(  # type: ignore[return-value]
        session.scalar(select(func.count()).select_from(model)) or 0
        for model in (Machine, Product, MaterialLot, ModelVersion)
    )


def test_seed_imports_demo_entries_and_mock_model(session: Session) -> None:
    report = seed(session, load_fleet(FLEET))
    assert report.inserted["machines"] == ["MC-01", "MC-03"]  # MC-09 has demo: false
    assert report.inserted["products"] == ["PP-JBOX-42"]
    assert report.inserted["material_lots"] == ["A-771", "A-772"]
    assert _counts(session) == (2, 1, 2, 1)
    lot = session.scalar(select(MaterialLot).where(MaterialLot.lot_code == "A-771"))
    assert lot is not None and lot.fleet_version == "fleet-test-0.0.1"


def test_seed_is_idempotent(session: Session) -> None:
    fleet = load_fleet(FLEET)
    seed(session, fleet)
    second = seed(session, fleet)
    assert all(not v for v in second.inserted.values())
    assert second.unchanged["machines"] == ["MC-01", "MC-03"]
    assert _counts(session) == (2, 1, 2, 1)


def test_missing_fleet_file_explains_owner(tmp_path: Path) -> None:
    with pytest.raises(FleetFileError, match="Role 1"):
        load_fleet(tmp_path / "fleet.yaml")


def test_invalid_fleet_file(tmp_path: Path) -> None:
    bad = tmp_path / "fleet.yaml"
    bad.write_text("fleet_version: x\nmachines:\n  - {machine_id: MC-1, machine_type: STEAM}\n")
    with pytest.raises(FleetFileError, match="invalid fleet file"):
        load_fleet(bad)


def test_cli_exit_codes(tmp_path: Path, database: Database, db_url: str) -> None:
    assert main(["--fleet", str(tmp_path / "none.yaml"), "--database-url", db_url]) == 2
    unmigrated = f"sqlite:///{(tmp_path / 'empty.db').as_posix()}"
    assert main(["--fleet", str(FLEET), "--database-url", unmigrated]) == 3
    assert main(["--fleet", str(FLEET), "--database-url", db_url]) == 0
    assert main(["--fleet", str(FLEET), "--database-url", db_url]) == 0  # idempotent
