"""Once Role 1 delivers app.contracts, the DB vocabulary must match it exactly (roadmap 7.2/7.6)."""

from __future__ import annotations

import importlib

import pytest

from app.db import vocab


def _enums() -> object:
    try:
        return importlib.import_module("app.contracts.enums")
    except ModuleNotFoundError:
        pytest.skip("app.contracts not delivered yet (R1-P1); vocab.py is a roadmap transcription")


def test_run_status_matches_contracts() -> None:
    enums = _enums()
    assert tuple(s.value for s in enums.RunStatus) == vocab.RUN_STATUSES  # type: ignore[attr-defined]


def test_risk_levels_match_contracts() -> None:
    enums = _enums()
    assert tuple(r.value for r in enums.RiskLevel) == vocab.RISK_LEVELS  # type: ignore[attr-defined]


def test_recipe_fields_match_contracts() -> None:
    _enums()
    recipe = importlib.import_module("app.contracts.recipe")
    assert tuple(recipe.ProcessRecipe.model_fields) == vocab.RECIPE_FIELDS
