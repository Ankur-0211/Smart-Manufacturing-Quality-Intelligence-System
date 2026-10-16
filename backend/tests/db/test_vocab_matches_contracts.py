"""The DB vocabulary comes from app.contracts; migration 0001 froze it into CHECK constraints.

If Role 1 changes an enum or the recipe, these tests fail until a migration follows (roadmap 10).
"""

from __future__ import annotations

from app.db import vocab

# Values persisted by backend/alembic/versions/0001_initial_schema.py.
MIGRATION_0001 = {
    "RUN_STATUSES": (
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
    ),
    "STAGE_NAMES": ("MATERIAL_CONDITIONING", "PLASTICIZING", "INJECTION", "PACKING", "COOLING"),
    "STAGE_SUBSTATES": ("PENDING", "RUNNING", "COMPLETED", "BLOCKED"),
    "RISK_LEVELS": ("NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"),
    "PREDICTION_LABELS": ("PASS", "FAIL"),
    "RUN_MODES": ("auto", "stepwise"),
    "SPEED_FACTORS": ("0.5x", "1x", "2x", "instant"),
    "INFERENCE_BACKENDS": ("real", "mock"),
    "MACHINE_TYPES": ("HYDRAULIC", "ELECTRIC", "HYBRID"),
}


def test_enum_vocabularies_match_migration_0001() -> None:
    for name, frozen in MIGRATION_0001.items():
        assert getattr(vocab, name) == frozen, f"{name} changed in app.contracts; add a migration"


def test_recipe_fields_match_run_parameters_columns() -> None:
    from app.db.models import RunParameters

    columns = {c.name for c in RunParameters.__table__.columns}
    assert set(vocab.RECIPE_FIELDS) <= columns
    assert len(vocab.RECIPE_FIELDS) == 23
