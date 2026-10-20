# Parameter Dictionary

Canonical vocabulary for the Smart Manufacturing Quality Intelligence System
(roadmap Sections 7.3-7.6, Plan Sections 2-3). Source of truth for limits:
`backend/app/domain/constraints.yaml` (this file never states numeric windows).

- Provenance for every row: `unvalidated` until R1-P1 task 4 attaches a citation or marks it `heuristic`.
- Defect-mode codes: **SS** short shot, **FL** flash, **SK** sink marks/voids,
  **WP** warpage, **SP** splay/silver streaks, **BD** burn marks/degradation.
- "Actionable" = may be changed by the recommendation engine. What-if may change any field.

## 1. Process setpoints (`kind = setpoint`, ProcessRecipe)

| Field | Unit | First stage | Actionable | Physical role | Related defects |
|---|---|---|---|---|---|
| `drying_time_h` | h | MATERIAL_CONDITIONING | yes | Time resin spends in the dryer; removes moisture | SP |
| `dryer_temp_c` | °C | MATERIAL_CONDITIONING | yes | Dryer air temperature; drying rate | SP |
| `barrel_temp_rear_c` | °C | PLASTICIZING | yes | Feed-zone temperature; start of the barrel profile | SS, BD |
| `barrel_temp_mid_c` | °C | PLASTICIZING | yes | Compression-zone temperature | SS, BD |
| `barrel_temp_front_c` | °C | PLASTICIZING | yes | Metering-zone temperature | SS, BD |
| `nozzle_temp_c` | °C | PLASTICIZING | yes | Nozzle temperature; freeze-off / drool risk | SS, BD |
| `melt_temp_c` | °C | PLASTICIZING | yes | Melt temperature; sets viscosity, degradation and moisture-splay risk | SS, FL, SP, BD |
| `screw_rpm` | rpm | PLASTICIZING | yes | Screw speed; shear heating and recovery time | BD, SP |
| `back_pressure_bar` | bar | PLASTICIZING | yes | Resistance during recovery; mixing and shear heat | BD, SP |
| `residence_time_s` | s | PLASTICIZING | yes (high change cost) | Time melt spends at temperature in the barrel | BD |
| `inj_velocity_mm_s` | mm/s | INJECTION | yes | Screw advance speed during fill; shear rate | SS, FL, BD |
| `inj_pressure_bar` | bar | INJECTION | yes | Pressure limit during fill | SS, FL |
| `fill_time_s` | s | INJECTION | yes | Duration of velocity-controlled fill | SS, FL |
| `shot_size_mm` | mm | INJECTION | yes | Screw stroke; volume of melt delivered | SS, FL |
| `switchover_position_mm` | mm | INJECTION | yes | Screw position at which fill hands over to packing | SS, FL, SK |
| `clamp_force_ton` | t | INJECTION | yes | Force holding the mold closed; must exceed cavity force | FL |
| `hold_pressure_bar` | bar | PACKING | yes | Packing pressure compensating shrinkage | SK, FL, WP |
| `hold_time_s` | s | PACKING | yes | Packing duration until the gate freezes | SK, WP |
| `cushion_mm` | mm | PACKING | yes | Residual melt in front of the screw; indicates packing effectiveness | SK |
| `mold_temp_c` | °C | PACKING (gate-freeze heuristic); dominant in COOLING | yes | Mold surface temperature; freeze rate and cooling rate | SK, WP |
| `cooling_time_s` | s | COOLING | yes | In-mold solidification before ejection | WP, SK |
| `cycle_time_s` | s | COOLING | derived by rule in what-if (UD-09) | Total cycle time | WP (via cooling) |
| `ejection_force_proxy` | dimensionless | COOLING | no (measured proxy) | Relative ejection effort; indicates sticking or under-cooling | WP |

## 2. Lot attributes (`kind = lot_attribute`, MaterialLot): all non-actionable

| Field | Unit | First stage | Physical role | Related defects |
|---|---|---|---|---|
| `material_lot_id` | code | context | Identity of the resin lot | none (identity only) |
| `resin_grade` | category | MATERIAL_CONDITIONING | Selects spec limits (melt window, degradation ceiling, moisture max) | SP, BD |
| `mfi` | g/10 min | MATERIAL_CONDITIONING | Melt flow index; viscosity expectation | SS, FL |
| `moisture_pct` | % | MATERIAL_CONDITIONING | Residual moisture; hydrolysis and steam | SP |
| `regrind_pct` | % | MATERIAL_CONDITIONING | Recycled content; property and viscosity variation | SS, SP |
| `colourant_pct` | % | MATERIAL_CONDITIONING | Pigment load; minor thermal and flow effect | BD |

## 3. Product and mold context (`kind = product_context`, ProductContext): all non-actionable

`mold_id == product_id` (Plan models product and mold as one entity).

| Field | Unit | First stage | Physical role | Related defects |
|---|---|---|---|---|
| `product_id` | code | context | Product and mold identity (e.g. `PP-JBOX-42`) | none (identity only) |
| `cavity_count` | count | INJECTION | Number of cavities; scales shot volume and clamp demand | SS, FL |
| `nominal_shot_weight_g` | g | context | Reference part weight | SS |
| `wall_thickness_mm` | mm | PACKING | Governs cooling time (thickness-squared family) and packing demand | SK, WP |
| `projected_area_cm2` | cm² | INJECTION | Per-cavity projected area; with cavity pressure sets required clamp force | FL |

`name` is a display label, not a model input.

## 4. Machine context (`kind = machine_context`, MachineProfile): all non-actionable

| Field | Unit | First stage | Physical role | Related defects |
|---|---|---|---|---|
| `machine_id` | code | context (fusion only) | Machine identity (e.g. `MC-03`); carries machine-specific bias | any |
| `machine_type` | category | context | HYDRAULIC / ELECTRIC / HYBRID | any |
| `tonnage_ton` | t | context | Nominal clamp tonnage | FL |
| `max_inj_pressure_bar` | bar | INJECTION | Pressure ceiling; used by the headroom rule | SS |
| `max_clamp_force_ton` | t | INJECTION | Clamp ceiling; used by the clamp guard | FL |
| `machine_age_days` | days | context (fusion only) | Wear proxy; snapshotted at run creation | any |
| `days_since_maintenance` | days | context (fusion only) | Maintenance-gap proxy; snapshotted at run creation | any |

## 5. Notes

- Fields with "context (fusion only)" invalidate only the fusion stage in what-if, because no stage module consumes them.
- Heuristic stage indicators (gate-freeze estimate, required cooling) are abstractions, not solved physics.
- Changing a name here requires a CCR (roadmap Section 10.4).