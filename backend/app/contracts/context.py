"""MachineProfile, ProductContext, MaterialLot, RunContext, ProcessInput
(roadmap Sections 7.3-7.7). Range limits are NOT hardcoded here (rule B6);
they live in constraints.yaml. Only structural checks are made."""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import MachineType
from .recipe import ProcessRecipe


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MachineProfile(_Frozen):
    machine_id: str
    machine_type: MachineType
    tonnage_ton: float = Field(gt=0)
    max_inj_pressure_bar: float = Field(gt=0)
    max_clamp_force_ton: float = Field(gt=0)
    machine_age_days: int = Field(ge=0)
    days_since_maintenance: int = Field(ge=0)


class ProductContext(_Frozen):
    product_id: str
    name: str
    cavity_count: int
    nominal_shot_weight_g: float
    wall_thickness_mm: float
    projected_area_cm2: float


class MaterialLot(_Frozen):
    material_lot_id: str
    resin_grade: str
    mfi: float
    moisture_pct: float
    regrind_pct: float
    colourant_pct: float


class RunContext(_Frozen):
    machine: MachineProfile
    product: ProductContext
    material_lot: MaterialLot


class ProcessInput(_Frozen):
    context: RunContext
    recipe: ProcessRecipe

    def flat(self) -> dict[str, Any]:
        """Canonical flat dict: the raw model input schema (Section 7.7)."""
        m, p, lot = self.context.machine, self.context.product, self.context.material_lot
        out: dict[str, Any] = {}
        out.update(m.model_dump(mode="python"))
        out.update(p.model_dump(mode="python", exclude={"name"}))
        out.update(lot.model_dump(mode="python"))
        out.update(self.recipe.model_dump(mode="python"))
        return out