"""Every ProcessRecipe field must be documented in docs/parameter_dictionary.md."""
from pathlib import Path

from app.contracts.recipe import RECIPE_FIELDS

DOC = Path(__file__).resolve().parents[3] / "docs" / "parameter_dictionary.md"


def test_every_recipe_field_is_documented():
    text = DOC.read_text(encoding="utf-8")
    missing = [f for f in RECIPE_FIELDS if f"`{f}`" not in text]
    assert not missing, f"undocumented fields: {missing}"


def test_context_fields_are_documented():
    text = DOC.read_text(encoding="utf-8")
    from app.contracts.context import MachineProfile, MaterialLot, ProductContext
    for model in (MachineProfile, MaterialLot, ProductContext):
        for name in model.model_fields:
            if name == "name":  # display label only, deliberately noted in prose
                continue
            assert f"`{name}`" in text, f"undocumented: {name}"