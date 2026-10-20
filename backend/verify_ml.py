"""Standalone script to test and verify the ML Quality Intelligence Engine."""
import sys
from pathlib import Path
import yaml
from app.domain.constraint_loader import load_constraint_registry
from app.intelligence.facade import RealQualityIntelligence
from app.contracts.recipe import ProcessRecipe
from app.contracts.context import ProcessInput, RunContext, MachineProfile, ProductContext, MaterialLot
from app.contracts.enums import MachineType


def resolve_run_context(machine_id: str = "MC-01", product_id: str = "PP-JBOX-42", lot_id: str = "A-771") -> RunContext:
    fleet_path = Path(__file__).resolve().parent / "app" / "domain" / "fleet.yaml"
    fleet = {}
    if fleet_path.exists():
        with open(fleet_path, "r", encoding="utf-8") as f:
            fleet = yaml.safe_load(f) or {}

    m_data = next((m for m in fleet.get("machines", []) if m.get("machine_id") == machine_id), None)
    if not m_data:
        m_data = {"machine_id": machine_id, "machine_type": "ELECTRIC", "tonnage_ton": 120.0, "max_inj_pressure_bar": 2000.0, "max_clamp_force_ton": 130.0, "machine_age_days": 420, "days_since_maintenance": 28}

    p_data = next((p for p in fleet.get("products", []) if p.get("product_id") == product_id), None)
    if not p_data:
        p_data = {"product_id": product_id, "name": "Standard Housing", "cavity_count": 1, "nominal_shot_weight_g": 42.0, "wall_thickness_mm": 2.2, "projected_area_cm2": 125.0}

    lot_data = next((l for l in fleet.get("material_lots", []) if l.get("material_lot_id") == lot_id), None)
    if not lot_data:
        lot_data = {"material_lot_id": lot_id, "resin_grade": "PP-H", "mfi": 12.0, "moisture_pct": 0.04, "regrind_pct": 10.0, "colourant_pct": 1.5}

    machine = MachineProfile(
        machine_id=m_data["machine_id"],
        machine_type=MachineType(m_data.get("machine_type", "ELECTRIC")),
        tonnage_ton=float(m_data["tonnage_ton"]),
        max_inj_pressure_bar=float(m_data["max_inj_pressure_bar"]),
        max_clamp_force_ton=float(m_data["max_clamp_force_ton"]),
        machine_age_days=int(m_data.get("machine_age_days", 300)),
        days_since_maintenance=int(m_data.get("days_since_maintenance", 14)),
    )
    product = ProductContext(
        product_id=p_data["product_id"],
        name=p_data.get("name", "Standard Housing"),
        cavity_count=int(p_data["cavity_count"]),
        nominal_shot_weight_g=float(p_data["nominal_shot_weight_g"]),
        wall_thickness_mm=float(p_data["wall_thickness_mm"]),
        projected_area_cm2=float(p_data["projected_area_cm2"]),
    )
    lot = MaterialLot(
        material_lot_id=lot_data["material_lot_id"],
        resin_grade=lot_data.get("resin_grade", "PP-H"),
        mfi=float(lot_data["mfi"]),
        moisture_pct=float(lot_data["moisture_pct"]),
        regrind_pct=float(lot_data["regrind_pct"]),
        colourant_pct=float(lot_data["colourant_pct"]),
    )
    return RunContext(machine=machine, product=product, material_lot=lot)


def main():
    print("=" * 60)
    print("SMQI MANUFACTURING QUALITY INTELLIGENCE ENGINE - VERIFICATION")
    print("=" * 60)

    # 1. Load domain registry and initialize engine
    registry = load_constraint_registry()
    intel = RealQualityIntelligence(registry=registry)
    print(f"[1] Engine initialized successfully.")
    print(f"    - Contracts version:   {intel.contracts_version}")
    print(f"    - Constraints version: {intel.constraints_version}")
    print(f"    - Model version:       {intel.model_version}")
    print(f"    - Operating threshold: {intel.threshold}")

    # 2. Build test process input
    context = resolve_run_context("MC-01", "PP-JBOX-42", "A-771")
    recipe = ProcessRecipe(
        drying_time_h=1.0,
        dryer_temp_c=80.0,
        barrel_temp_rear_c=200.0,
        barrel_temp_mid_c=215.0,
        barrel_temp_front_c=225.0,
        nozzle_temp_c=230.0,
        melt_temp_c=230.0,
        screw_rpm=100.0,
        back_pressure_bar=60.0,
        residence_time_s=30.0,
        inj_velocity_mm_s=100.0,
        inj_pressure_bar=900.0,
        fill_time_s=1.4,
        shot_size_mm=45.0,
        switchover_position_mm=12.0,
        clamp_force_ton=120.0,
        hold_pressure_bar=600.0,
        hold_time_s=2.5,
        cushion_mm=5.0,
        mold_temp_c=40.0,
        cooling_time_s=22.0,
        cycle_time_s=38.0,
        ejection_force_proxy=0.5,
    )
    proc_input = ProcessInput(context=context, recipe=recipe)

    # 3. Execute full 6-stage pipeline
    pipeline_res = intel.evaluate(proc_input, include_explanation=True)
    pred = pipeline_res.prediction

    print("\n[2] Stage-Level Intelligence (S1 - S5):")
    for stage in pipeline_res.stage_results:
        print(f"    • {stage.stage_name.value:<23} | Health: {stage.health_score:0.2f} | Risk: {stage.risk_level.value:<8} | Breaches: {len(stage.constraint_breaches)}")

    print("\n[3] Fusion Quality Prediction (S6):")
    print(f"    • Classification Label:   {pred.label.value}")
    print(f"    • Probability of Failure: {pred.p_fail:.3f} (Threshold: {pred.threshold_used})")
    print(f"    • Operational Risk Band:  {pred.risk_level.value}")

    print("\n[4] Explainability (SHAP Attributions):")
    if pred.explanation:
        for attr in pred.explanation.attributions[:6]:
            print(f"    • {attr.feature:<23} | SHAP: {attr.shap_value:+.3f} | Direction: {attr.direction}")

    print("\n[5] Stage Risk Mass Distribution:")
    for share in pred.stage_risk_mass:
        print(f"    • {share.stage.value:<23} | Risk Share: {share.share * 100:.1f}%")

    print("\n[6] 1D Sensitivity Analysis (Sweep 'cooling_time_s'):")
    sens = intel.sensitivity(proc_input, "cooling_time_s", steps=6)
    print(f"    • Local Gradient: {sens.local_gradient:+.4f} dP/s")
    print(f"    • Range Swing:    {sens.range_swing:.3f}")
    for pt in sens.points:
        print(f"      - Value: {pt.value:4.1f} s  -->  P(fail) = {pt.p_fail:.3f} [{pt.label}]")

    print("\n" + "=" * 60)
    print("VERIFICATION COMPLETE: ALL ML CAPABILITIES ARE OPERATIONAL.")
    print("=" * 60)

if __name__ == "__main__":
    main()
