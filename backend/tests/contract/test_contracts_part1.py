import pytest
from pydantic import ValidationError

from app.contracts.enums import (INTELLIGENCE_STAGES, RiskLevel, StageName)
from app.contracts.recipe import RECIPE_FIELDS, ProcessRecipe
from app.contracts.errors import InvalidInputError, IntelligenceError


def test_stage_order_and_index():
    assert StageName.MATERIAL_CONDITIONING.sequence_index == 1
    assert StageName.QUALITY_INSPECTION.sequence_index == 6
    assert len(INTELLIGENCE_STAGES) == 5


def test_risk_ordinals():
    assert [r.ordinal for r in RiskLevel] == [0, 1, 2, 3, 4]


def test_recipe_has_23_fields_and_forbids_extras():
    assert len(RECIPE_FIELDS) == 23
    with pytest.raises(ValidationError):
        ProcessRecipe(**{f: 1.0 for f in RECIPE_FIELDS}, bogus=1)


def test_recipe_frozen():
    r = ProcessRecipe(**{f: 1.0 for f in RECIPE_FIELDS})
    with pytest.raises(ValidationError):
        r.melt_temp_c = 2.0


def test_error_codes():
    e = InvalidInputError("x", field="melt_temp_c")
    assert isinstance(e, IntelligenceError) and e.code == "INVALID_INTELLIGENCE_INPUT"