"""ProcessRecipe: operator-controlled setpoints (roadmap Section 7.6).
Field names are canonical and identical to registry keys and DB columns."""
from pydantic import BaseModel, ConfigDict


class ProcessRecipe(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    # MATERIAL_CONDITIONING
    drying_time_h: float
    dryer_temp_c: float
    # PLASTICIZING
    barrel_temp_rear_c: float
    barrel_temp_mid_c: float
    barrel_temp_front_c: float
    nozzle_temp_c: float
    melt_temp_c: float
    screw_rpm: float
    back_pressure_bar: float
    residence_time_s: float
    # INJECTION
    inj_velocity_mm_s: float
    inj_pressure_bar: float
    fill_time_s: float
    shot_size_mm: float
    switchover_position_mm: float
    clamp_force_ton: float
    # PACKING
    hold_pressure_bar: float
    hold_time_s: float
    cushion_mm: float
    mold_temp_c: float  # first consumed at PACKING (gate-freeze heuristic)
    # COOLING
    cooling_time_s: float
    cycle_time_s: float
    ejection_force_proxy: float


RECIPE_FIELDS: tuple[str, ...] = tuple(ProcessRecipe.model_fields.keys())