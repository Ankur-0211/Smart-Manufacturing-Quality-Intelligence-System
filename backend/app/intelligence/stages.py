"""Stateless, deterministic stage intelligence implementations for S1-S5 (roadmap Section 7.10)."""
import math
import time
from typing import Any

from ..contracts.context import ProcessInput
from ..contracts.enums import (
    AnomalyMethod,
    ConstraintSeverity,
    DataProvenance,
    RiskLevel,
    StageName,
    StageSubstate,
)
from ..contracts.stage import ConstraintBreach, StageAnomaly, StageResult, UpstreamContext
from ..domain.constraint_loader import ConstraintRegistry


def health_to_risk(health: float, has_critical: bool) -> tuple[RiskLevel, int]:
    """Map health score to RiskLevel using standard bands.
    NORMAL >= 0.90, LOW >= 0.70, MEDIUM >= 0.50, HIGH >= 0.30, CRITICAL < 0.30.
    Any critical breach escalates to CRITICAL."""
    if has_critical:
        return RiskLevel.CRITICAL, 4
    if health >= 0.90:
        return RiskLevel.NORMAL, 0
    elif health >= 0.70:
        return RiskLevel.LOW, 1
    elif health >= 0.50:
        return RiskLevel.MEDIUM, 2
    elif health >= 0.30:
        return RiskLevel.HIGH, 3
    else:
        return RiskLevel.CRITICAL, 4


# --- STAGE 1: MATERIAL CONDITIONING ---
def evaluate_material_stage(
    inp: ProcessInput, upstream: UpstreamContext, registry: ConstraintRegistry
) -> StageResult:
    start = time.perf_counter()
    lot = inp.context.material_lot
    recipe = inp.recipe
    grade = registry.get_resin_grade(lot.resin_grade)

    indicators: dict[str, Any] = {}
    ind_prov: dict[str, DataProvenance] = {}
    notes: list[str] = []

    spec_moist = float(grade.get("moisture_spec_max_pct", 0.10))
    dryness_margin = spec_moist - lot.moisture_pct
    indicators["dryness_margin"] = round(dryness_margin, 4)
    ind_prov["dryness_margin"] = DataProvenance.SPECIFICATION_DERIVED

    mfi_nom = float(grade.get("mfi_nominal", 12.0))
    mfi_z = (lot.mfi - mfi_nom) / (mfi_nom * 0.15)
    indicators["mfi_z"] = round(mfi_z, 2)
    ind_prov["mfi_z"] = DataProvenance.HEURISTIC

    moisture_z = (lot.moisture_pct - 0.05) / 0.03
    indicators["moisture_z"] = round(moisture_z, 2)
    ind_prov["moisture_z"] = DataProvenance.HEURISTIC

    # Moisture risk indicator
    moisture_risk = max(0.0, min(1.0, lot.moisture_pct / (spec_moist * 1.5)))
    indicators["moisture_risk"] = round(moisture_risk, 3)
    ind_prov["moisture_risk"] = DataProvenance.HEURISTIC

    regrind_margin = 20.0 - lot.regrind_pct
    indicators["regrind_margin"] = round(regrind_margin, 1)
    ind_prov["regrind_margin"] = DataProvenance.SPECIFICATION_DERIVED

    if lot.mfi < mfi_nom * 0.85:
        viscosity_class = "HIGH"
    elif lot.mfi > mfi_nom * 1.15:
        viscosity_class = "LOW"
    else:
        viscosity_class = "NOMINAL"
    indicators["viscosity_class"] = viscosity_class
    ind_prov["viscosity_class"] = DataProvenance.HEURISTIC

    moisture_flag = lot.moisture_pct > spec_moist
    if moisture_flag:
        notes.append(f"Lot moisture ({lot.moisture_pct}%) exceeds spec ({spec_moist}%). Elevated splay risk.")
    if lot.regrind_pct > 15.0:
        notes.append(f"Regrind proportion ({lot.regrind_pct}%) is high; potential MFI batch variance.")

    # Upstream state published
    up_out = UpstreamContext(
        viscosity_class=viscosity_class,
        moisture_flag=moisture_flag,
    )

    # Hard constraints & breaches
    breaches, blocked, block_reason = registry.check_hard_constraints(
        StageName.MATERIAL_CONDITIONING, inp, indicators
    )

    # Health penalty
    penalty = 0.0
    if lot.moisture_pct > spec_moist:
        penalty += 0.35 * min(1.0, (lot.moisture_pct - spec_moist) / 0.05)
    if abs(mfi_z) > 2.0:
        penalty += 0.20 * min(1.0, (abs(mfi_z) - 2.0) / 2.0)
    if recipe.drying_time_h < 0.5 and lot.moisture_pct > 0.05:
        penalty += 0.20
    health = max(0.0, min(1.0, 1.0 - penalty))

    has_crit = any(b.severity == ConstraintSeverity.CRITICAL for b in breaches) or blocked
    risk, r_ord = health_to_risk(health, has_crit)

    # Anomaly check
    anom_flag = abs(moisture_z) > 2.5 or abs(mfi_z) > 2.5
    anomaly = StageAnomaly(
        flag=anom_flag,
        score=round(min(1.0, max(abs(moisture_z), abs(mfi_z)) / 4.0), 2),
        method=AnomalyMethod.ZSCORE,
        contributors=[{"feature": "moisture_pct", "deviation": round(moisture_z, 2)}] if abs(moisture_z) > 2.0 else [],
        note="Material attribute outside normal lot variance" if anom_flag else "",
    )

    compute_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return StageResult(
        stage_name=StageName.MATERIAL_CONDITIONING,
        sequence_index=1,
        substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
        inputs_used={
            "moisture_pct": lot.moisture_pct,
            "mfi": lot.mfi,
            "regrind_pct": lot.regrind_pct,
            "drying_time_h": recipe.drying_time_h,
            "dryer_temp_c": recipe.dryer_temp_c,
            "colourant_pct": lot.colourant_pct,
            "resin_grade": lot.resin_grade,
        },
        upstream_in=upstream,
        upstream_out=up_out,
        health_score=round(health, 3),
        risk_level=risk,
        risk_ordinal=r_ord,
        anomaly=anomaly,
        indicators=indicators,
        indicator_provenance=ind_prov,
        notes=notes,
        constraint_breaches=breaches,
        blocked=blocked,
        block_reason=block_reason,
        module_version="1.0.0",
        constraints_version=registry.version,
        compute_ms=compute_ms,
    )


# --- STAGE 2: PLASTICIZING / THERMAL ---
def evaluate_plasticizing_stage(
    inp: ProcessInput, upstream: UpstreamContext, registry: ConstraintRegistry
) -> StageResult:
    start = time.perf_counter()
    recipe = inp.recipe
    lot = inp.context.material_lot
    grade = registry.get_resin_grade(lot.resin_grade)

    indicators: dict[str, Any] = {}
    ind_prov: dict[str, DataProvenance] = {}
    notes: list[str] = []

    # Thermal profile slope (rear to nozzle)
    temp_slope = recipe.nozzle_temp_c - recipe.barrel_temp_rear_c
    indicators["temp_profile_slope"] = round(temp_slope, 1)
    ind_prov["temp_profile_slope"] = DataProvenance.SPECIFICATION_DERIVED

    profile_monotonic = (
        recipe.barrel_temp_rear_c <= recipe.barrel_temp_mid_c <= recipe.barrel_temp_front_c <= recipe.nozzle_temp_c + 5.0
    )
    indicators["profile_monotonic"] = profile_monotonic
    ind_prov["profile_monotonic"] = DataProvenance.HEURISTIC
    if not profile_monotonic:
        notes.append("Inverted barrel temperature gradient detected. Potential un-melted granules entering metering zone.")

    # Viscous shear dissipation heat offset
    shear_heat = (recipe.screw_rpm / 100.0) * (recipe.back_pressure_bar / 80.0) * 8.0
    effective_melt_c = recipe.melt_temp_c + shear_heat
    indicators["shear_heat_offset_c"] = round(shear_heat, 1)
    ind_prov["shear_heat_offset_c"] = DataProvenance.HEURISTIC
    indicators["effective_melt_temp_c"] = round(effective_melt_c, 1)
    ind_prov["effective_melt_temp_c"] = DataProvenance.HEURISTIC

    # Residence time degradation exposure
    degradation_exp = max(0.0, (effective_melt_c - 240.0) / 45.0) * (recipe.residence_time_s / 60.0)
    indicators["degradation_exposure"] = round(degradation_exp, 3)
    ind_prov["degradation_exposure"] = DataProvenance.HEURISTIC

    # Splay risk
    splay_risk = 0.05
    if upstream.moisture_flag:
        splay_risk += 0.45
    if effective_melt_c > 260.0:
        splay_risk += 0.30
    indicators["splay_risk"] = round(min(1.0, splay_risk), 3)
    ind_prov["splay_risk"] = DataProvenance.HEURISTIC

    # Viscosity proxy
    visc_nom = 1.0
    if upstream.viscosity_class == "HIGH":
        visc_nom *= 1.25
    elif upstream.viscosity_class == "LOW":
        visc_nom *= 0.80
    # Arrhenius temperature adjustment
    visc_proxy = visc_nom * math.exp(-0.015 * (effective_melt_c - 230.0))
    indicators["viscosity_proxy"] = round(visc_proxy, 3)
    ind_prov["viscosity_proxy"] = DataProvenance.HEURISTIC

    # Upstream state published
    up_out = UpstreamContext(
        viscosity_class=upstream.viscosity_class,
        moisture_flag=upstream.moisture_flag,
        effective_melt_temp_c=round(effective_melt_c, 1),
        viscosity_proxy=round(visc_proxy, 3),
    )

    breaches, blocked, block_reason = registry.check_hard_constraints(
        StageName.PLASTICIZING, inp, indicators
    )

    # Health penalty
    penalty = 0.0
    melt_win = grade.get("melt_window_c", [200, 260])
    if recipe.melt_temp_c < melt_win[0]:
        penalty += 0.35 * min(1.0, (melt_win[0] - recipe.melt_temp_c) / 15.0)
    elif recipe.melt_temp_c > melt_win[1]:
        penalty += 0.35 * min(1.0, (recipe.melt_temp_c - melt_win[1]) / 20.0)
    if not profile_monotonic:
        penalty += 0.20
    if degradation_exp > 0.5:
        penalty += 0.25 * min(1.0, degradation_exp)
    health = max(0.0, min(1.0, 1.0 - penalty))

    has_crit = any(b.severity == ConstraintSeverity.CRITICAL for b in breaches) or blocked
    risk, r_ord = health_to_risk(health, has_crit)

    anom_flag = degradation_exp > 0.85
    anomaly = StageAnomaly(
        flag=anom_flag,
        score=round(min(1.0, degradation_exp), 2),
        method=AnomalyMethod.SPEC_LIMIT,
        contributors=[{"feature": "melt_temp_c", "deviation": round(effective_melt_c - 230.0, 1)}] if anom_flag else [],
        note="Excessive thermal degradation exposure" if anom_flag else "",
    )

    compute_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return StageResult(
        stage_name=StageName.PLASTICIZING,
        sequence_index=2,
        substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
        inputs_used={
            "barrel_temp_rear_c": recipe.barrel_temp_rear_c,
            "barrel_temp_mid_c": recipe.barrel_temp_mid_c,
            "barrel_temp_front_c": recipe.barrel_temp_front_c,
            "nozzle_temp_c": recipe.nozzle_temp_c,
            "melt_temp_c": recipe.melt_temp_c,
            "screw_rpm": recipe.screw_rpm,
            "back_pressure_bar": recipe.back_pressure_bar,
            "residence_time_s": recipe.residence_time_s,
        },
        upstream_in=upstream,
        upstream_out=up_out,
        health_score=round(health, 3),
        risk_level=risk,
        risk_ordinal=r_ord,
        anomaly=anomaly,
        indicators=indicators,
        indicator_provenance=ind_prov,
        notes=notes,
        constraint_breaches=breaches,
        blocked=blocked,
        block_reason=block_reason,
        module_version="1.0.0",
        constraints_version=registry.version,
        compute_ms=compute_ms,
    )


# --- STAGE 3: INJECTION / FILL ---
def evaluate_injection_stage(
    inp: ProcessInput, upstream: UpstreamContext, registry: ConstraintRegistry
) -> StageResult:
    start = time.perf_counter()
    recipe = inp.recipe
    prod = inp.context.product
    mach = inp.context.machine

    indicators: dict[str, Any] = {}
    ind_prov: dict[str, DataProvenance] = {}
    notes: list[str] = []

    visc = upstream.viscosity_proxy or 1.0
    # Estimated cavity pressure
    # P_cav = inj_pressure_bar * (1 - fill_time / (fill_time + 1.5)) * (1 / visc)
    cavity_pressure = recipe.inj_pressure_bar * 0.38 * (1.0 / max(0.5, visc))
    indicators["cavity_pressure_estimate_bar"] = round(cavity_pressure, 1)
    ind_prov["cavity_pressure_estimate_bar"] = DataProvenance.HEURISTIC

    # Pressure headroom
    headroom = (mach.max_inj_pressure_bar - recipe.inj_pressure_bar) / mach.max_inj_pressure_bar
    indicators["pressure_headroom"] = round(headroom, 3)
    ind_prov["pressure_headroom"] = DataProvenance.SPECIFICATION_DERIVED

    # Fill completion proxy
    volumetric_dose = recipe.shot_size_mm - recipe.switchover_position_mm
    fill_completion = min(1.0, (volumetric_dose / (recipe.shot_size_mm * 0.85)))
    indicators["fill_completion_proxy"] = round(fill_completion, 3)
    ind_prov["fill_completion_proxy"] = DataProvenance.HEURISTIC

    # Short shot risk
    short_shot_risk = 0.05
    if recipe.fill_time_s < 0.7:
        short_shot_risk += 0.35
    if recipe.inj_velocity_mm_s < 45.0:
        short_shot_risk += 0.30
    if visc > 1.3:
        short_shot_risk += 0.25
    indicators["short_shot_risk"] = round(min(1.0, short_shot_risk), 3)
    ind_prov["short_shot_risk"] = DataProvenance.HEURISTIC

    # Flash risk
    flash_risk = 0.05
    if recipe.inj_pressure_bar > 1300.0:
        flash_risk += 0.35
    indicators["flash_risk"] = round(min(1.0, flash_risk), 3)
    ind_prov["flash_risk"] = DataProvenance.HEURISTIC

    # Upstream state published
    up_out = UpstreamContext(
        viscosity_class=upstream.viscosity_class,
        moisture_flag=upstream.moisture_flag,
        effective_melt_temp_c=upstream.effective_melt_temp_c,
        viscosity_proxy=upstream.viscosity_proxy,
        fill_completion_proxy=round(fill_completion, 3),
        cavity_pressure_estimate_bar=round(cavity_pressure, 1),
    )

    breaches, blocked, block_reason = registry.check_hard_constraints(
        StageName.INJECTION, inp, indicators
    )

    # Health penalty
    penalty = 0.0
    if short_shot_risk > 0.4:
        penalty += 0.35 * short_shot_risk
    if flash_risk > 0.4:
        penalty += 0.35 * flash_risk
    if headroom < 0.10:
        penalty += 0.25 * (1.0 - headroom / 0.10)
    health = max(0.0, min(1.0, 1.0 - penalty))

    has_crit = any(b.severity == ConstraintSeverity.CRITICAL for b in breaches) or blocked
    risk, r_ord = health_to_risk(health, has_crit)

    anom_flag = headroom < 0.05 or short_shot_risk > 0.70
    anomaly = StageAnomaly(
        flag=anom_flag,
        score=round(max(short_shot_risk, flash_risk), 2),
        method=AnomalyMethod.SPEC_LIMIT,
        contributors=[{"feature": "inj_pressure_bar", "deviation": round(recipe.inj_pressure_bar, 1)}] if anom_flag else [],
        note="Elevated risk of cavity underfill or hydraulic saturation" if anom_flag else "",
    )

    compute_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return StageResult(
        stage_name=StageName.INJECTION,
        sequence_index=3,
        substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
        inputs_used={
            "inj_velocity_mm_s": recipe.inj_velocity_mm_s,
            "inj_pressure_bar": recipe.inj_pressure_bar,
            "fill_time_s": recipe.fill_time_s,
            "shot_size_mm": recipe.shot_size_mm,
            "switchover_position_mm": recipe.switchover_position_mm,
            "clamp_force_ton": recipe.clamp_force_ton,
            "projected_area_cm2": prod.projected_area_cm2,
            "cavity_count": prod.cavity_count,
        },
        upstream_in=upstream,
        upstream_out=up_out,
        health_score=round(health, 3),
        risk_level=risk,
        risk_ordinal=r_ord,
        anomaly=anomaly,
        indicators=indicators,
        indicator_provenance=ind_prov,
        notes=notes,
        constraint_breaches=breaches,
        blocked=blocked,
        block_reason=block_reason,
        module_version="1.0.0",
        constraints_version=registry.version,
        compute_ms=compute_ms,
    )


# --- STAGE 4: PACKING / HOLDING ---
def evaluate_packing_stage(
    inp: ProcessInput, upstream: UpstreamContext, registry: ConstraintRegistry
) -> StageResult:
    start = time.perf_counter()
    recipe = inp.recipe
    prod = inp.context.product

    indicators: dict[str, Any] = {}
    ind_prov: dict[str, DataProvenance] = {}
    notes: list[str] = []

    # Packing integral
    packing_integral = recipe.hold_pressure_bar * recipe.hold_time_s
    indicators["packing_integral"] = round(packing_integral, 1)
    ind_prov["packing_integral"] = DataProvenance.HEURISTIC

    # Gate freeze estimate: Ballman-Dutton thermal diffusion
    # t_freeze ~ (h^2 / (pi^2 * alpha)) * ln(...) -> approx 0.85 * wall_thickness^1.9
    gate_freeze_s = 0.85 * (prod.wall_thickness_mm ** 1.9)
    indicators["gate_freeze_estimate_s"] = round(gate_freeze_s, 2)
    ind_prov["gate_freeze_estimate_s"] = DataProvenance.HEURISTIC

    hold_vs_freeze = recipe.hold_time_s / max(0.5, gate_freeze_s)
    indicators["hold_vs_freeze_ratio"] = round(hold_vs_freeze, 2)
    ind_prov["hold_vs_freeze_ratio"] = DataProvenance.HEURISTIC

    # Sink & void risk
    sink_risk = 0.05
    if hold_vs_freeze < 0.85:
        sink_risk += 0.45 * (1.0 - hold_vs_freeze / 0.85)
    if recipe.hold_pressure_bar < 400.0:
        sink_risk += 0.35 * (1.0 - recipe.hold_pressure_bar / 400.0)
    indicators["sink_void_risk"] = round(min(1.0, sink_risk), 3)
    ind_prov["sink_void_risk"] = DataProvenance.HEURISTIC

    # Residual stress proxy
    residual_stress = (recipe.hold_pressure_bar / 800.0) * math.exp(-0.02 * recipe.mold_temp_c)
    indicators["residual_stress_proxy"] = round(residual_stress, 3)
    ind_prov["residual_stress_proxy"] = DataProvenance.HEURISTIC

    # Upstream state published
    up_out = UpstreamContext(
        viscosity_class=upstream.viscosity_class,
        moisture_flag=upstream.moisture_flag,
        effective_melt_temp_c=upstream.effective_melt_temp_c,
        viscosity_proxy=upstream.viscosity_proxy,
        fill_completion_proxy=upstream.fill_completion_proxy,
        cavity_pressure_estimate_bar=upstream.cavity_pressure_estimate_bar,
        residual_stress_proxy=round(residual_stress, 3),
    )

    breaches, blocked, block_reason = registry.check_hard_constraints(
        StageName.PACKING, inp, indicators
    )

    penalty = 0.0
    if sink_risk > 0.30:
        penalty += 0.40 * sink_risk
    if recipe.cushion_mm < 2.0 or recipe.cushion_mm > 15.0:
        penalty += 0.25
    health = max(0.0, min(1.0, 1.0 - penalty))

    has_crit = any(b.severity == ConstraintSeverity.CRITICAL for b in breaches) or blocked
    risk, r_ord = health_to_risk(health, has_crit)

    anom_flag = sink_risk > 0.65
    anomaly = StageAnomaly(
        flag=anom_flag,
        score=round(sink_risk, 2),
        method=AnomalyMethod.IQR,
        contributors=[{"feature": "hold_pressure_bar", "deviation": round(recipe.hold_pressure_bar - 550.0, 1)}] if anom_flag else [],
        note="High sink mark / shrinkage void risk detected" if anom_flag else "",
    )

    compute_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return StageResult(
        stage_name=StageName.PACKING,
        sequence_index=4,
        substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
        inputs_used={
            "hold_pressure_bar": recipe.hold_pressure_bar,
            "hold_time_s": recipe.hold_time_s,
            "cushion_mm": recipe.cushion_mm,
            "mold_temp_c": recipe.mold_temp_c,
            "wall_thickness_mm": prod.wall_thickness_mm,
        },
        upstream_in=upstream,
        upstream_out=up_out,
        health_score=round(health, 3),
        risk_level=risk,
        risk_ordinal=r_ord,
        anomaly=anomaly,
        indicators=indicators,
        indicator_provenance=ind_prov,
        notes=notes,
        constraint_breaches=breaches,
        blocked=blocked,
        block_reason=block_reason,
        module_version="1.0.0",
        constraints_version=registry.version,
        compute_ms=compute_ms,
    )


# --- STAGE 5: COOLING / EJECTION ---
def evaluate_cooling_stage(
    inp: ProcessInput, upstream: UpstreamContext, registry: ConstraintRegistry
) -> StageResult:
    start = time.perf_counter()
    recipe = inp.recipe
    prod = inp.context.product

    indicators: dict[str, Any] = {}
    ind_prov: dict[str, DataProvenance] = {}
    notes: list[str] = []

    # Required cooling estimate
    req_cooling = 2.0 * (prod.wall_thickness_mm ** 2)
    indicators["required_cooling_estimate_s"] = round(req_cooling, 1)
    ind_prov["required_cooling_estimate_s"] = DataProvenance.HEURISTIC

    cooling_adequacy = recipe.cooling_time_s / max(1.0, req_cooling)
    indicators["cooling_adequacy"] = round(cooling_adequacy, 2)
    ind_prov["cooling_adequacy"] = DataProvenance.HEURISTIC

    # Warpage risk
    warp_risk = 0.05
    if cooling_adequacy < 0.90:
        warp_risk += 0.45 * (1.0 - cooling_adequacy / 0.90)
    if recipe.mold_temp_c > 50.0:
        warp_risk += 0.30 * ((recipe.mold_temp_c - 50.0) / 35.0)
    if (upstream.residual_stress_proxy or 0.5) > 1.2:
        warp_risk += 0.20
    indicators["warp_risk"] = round(min(1.0, warp_risk), 3)
    ind_prov["warp_risk"] = DataProvenance.HEURISTIC

    # Cycle consistency
    modelled_sum = recipe.fill_time_s + recipe.hold_time_s + recipe.cooling_time_s + 2.5  # mold open/close + eject
    cycle_balance = recipe.cycle_time_s - modelled_sum
    indicators["cycle_balance"] = round(cycle_balance, 1)
    ind_prov["cycle_balance"] = DataProvenance.HEURISTIC

    breaches, blocked, block_reason = registry.check_hard_constraints(
        StageName.COOLING, inp, indicators
    )

    penalty = 0.0
    if warp_risk > 0.30:
        penalty += 0.45 * warp_risk
    if cooling_adequacy < 0.85:
        penalty += 0.35 * (1.0 - cooling_adequacy / 0.85)
    health = max(0.0, min(1.0, 1.0 - penalty))

    has_crit = any(b.severity == ConstraintSeverity.CRITICAL for b in breaches) or blocked
    risk, r_ord = health_to_risk(health, has_crit)

    anom_flag = warp_risk > 0.65
    anomaly = StageAnomaly(
        flag=anom_flag,
        score=round(warp_risk, 2),
        method=AnomalyMethod.IQR,
        contributors=[{"feature": "cooling_time_s", "deviation": round(recipe.cooling_time_s - req_cooling, 1)}] if anom_flag else [],
        note="Insufficient cooling duration; elevated warpage probability" if anom_flag else "",
    )

    compute_ms = round((time.perf_counter() - start) * 1000.0, 2)
    return StageResult(
        stage_name=StageName.COOLING,
        sequence_index=5,
        substate=StageSubstate.BLOCKED if blocked else StageSubstate.COMPLETED,
        inputs_used={
            "mold_temp_c": recipe.mold_temp_c,
            "cooling_time_s": recipe.cooling_time_s,
            "cycle_time_s": recipe.cycle_time_s,
            "ejection_force_proxy": recipe.ejection_force_proxy,
            "wall_thickness_mm": prod.wall_thickness_mm,
        },
        upstream_in=upstream,
        upstream_out=upstream,
        health_score=round(health, 3),
        risk_level=risk,
        risk_ordinal=r_ord,
        anomaly=anomaly,
        indicators=indicators,
        indicator_provenance=ind_prov,
        notes=notes,
        constraint_breaches=breaches,
        blocked=blocked,
        block_reason=block_reason,
        module_version="1.0.0",
        constraints_version=registry.version,
        compute_ms=compute_ms,
    )
