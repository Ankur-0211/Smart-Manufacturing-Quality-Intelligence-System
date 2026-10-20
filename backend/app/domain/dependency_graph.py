"""Process stage dependency graph and partial re-simulation invalidation (roadmap Section 8.4)."""
from typing import Iterable
from ..contracts.enums import STAGE_ORDER, StageName

# Mapping of every recipe / context knob to its earliest consuming stage
PARAM_TO_STAGE: dict[str, StageName] = {
    # S1 Material Conditioning
    "drying_time_h": StageName.MATERIAL_CONDITIONING,
    "dryer_temp_c": StageName.MATERIAL_CONDITIONING,
    "moisture_pct": StageName.MATERIAL_CONDITIONING,
    "mfi": StageName.MATERIAL_CONDITIONING,
    "regrind_pct": StageName.MATERIAL_CONDITIONING,
    "colourant_pct": StageName.MATERIAL_CONDITIONING,
    "resin_grade": StageName.MATERIAL_CONDITIONING,
    # S2 Plasticizing / Thermal
    "barrel_temp_rear_c": StageName.PLASTICIZING,
    "barrel_temp_mid_c": StageName.PLASTICIZING,
    "barrel_temp_front_c": StageName.PLASTICIZING,
    "nozzle_temp_c": StageName.PLASTICIZING,
    "melt_temp_c": StageName.PLASTICIZING,
    "screw_rpm": StageName.PLASTICIZING,
    "back_pressure_bar": StageName.PLASTICIZING,
    "residence_time_s": StageName.PLASTICIZING,
    # S3 Injection / Fill
    "inj_velocity_mm_s": StageName.INJECTION,
    "inj_pressure_bar": StageName.INJECTION,
    "fill_time_s": StageName.INJECTION,
    "shot_size_mm": StageName.INJECTION,
    "switchover_position_mm": StageName.INJECTION,
    "clamp_force_ton": StageName.INJECTION,
    # S4 Packing / Holding (Note: mold_temp_c is first consumed in S4 gate-freeze heuristic)
    "hold_pressure_bar": StageName.PACKING,
    "hold_time_s": StageName.PACKING,
    "cushion_mm": StageName.PACKING,
    "mold_temp_c": StageName.PACKING,
    # S5 Cooling / Ejection
    "cooling_time_s": StageName.COOLING,
    "cycle_time_s": StageName.COOLING,
    "ejection_force_proxy": StageName.COOLING,
    # Context changes trigger S1 recomputation
    "machine_id": StageName.MATERIAL_CONDITIONING,
    "product_id": StageName.MATERIAL_CONDITIONING,
    "material_lot_id": StageName.MATERIAL_CONDITIONING,
    "wall_thickness_mm": StageName.PACKING,  # thick section packing and cooling
}


def get_earliest_stage(changed_params: Iterable[str]) -> StageName | None:
    """Find the earliest stage in the physical sequence affected by the changes."""
    earliest_idx = len(STAGE_ORDER)
    found_stage: StageName | None = None

    for param in changed_params:
        stage = PARAM_TO_STAGE.get(param)
        if stage is not None:
            idx = STAGE_ORDER.index(stage)
            if idx < earliest_idx:
                earliest_idx = idx
                found_stage = stage

    return found_stage


def invalidated_stages(changed_params: Iterable[str]) -> list[StageName]:
    """Return all stages from the earliest invalidated stage through S5 and S6."""
    earliest = get_earliest_stage(changed_params)
    if earliest is None:
        return [StageName.QUALITY_INSPECTION]

    start_idx = STAGE_ORDER.index(earliest)
    # Recompute from earliest stage up to and including QUALITY_INSPECTION
    return list(STAGE_ORDER[start_idx:])
