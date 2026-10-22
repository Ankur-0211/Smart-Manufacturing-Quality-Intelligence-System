# UI copy for Role 1 to confirm (R2-P6 handoff)

The Process Control screen shows wording that describes Role 1's outputs. Please confirm or correct each item; corrections become a small UI change on `role-2-application`. Screenshots: `docs/screenshots/`.

| # | Where | Current wording | Question for Role 1 |
|---|---|---|---|
| 1 | Result card, P(fail) | `0.24 (calibrated)` | Is `p_fail` from `fusion-1.0.0` actually calibrated? If not, this label must change (claim discipline, roadmap §1.7) |
| 2 | Result card, label | `Prediction: PASS` / `Model label: FAIL` (under NOT RELEASABLE) | OK once the label follows the threshold (CCR-004 #2)? |
| 3 | Result card, anomaly | `Anomaly status: Not evaluated` (when `anomaly_global` is null) | Correct while global anomaly detection is not part of the interface (CCR-004 #8)? |
| 4 | Result card, risk origin | `Risk origin: MATERIAL 20% \| THERMAL 20% …` from `stage_risk_mass` | It is uniform for many inputs. Is that intended? (CCR-004 #3) |
| 5 | Stage panel, indicators | Raw indicator keys (e.g. `cavity_pressure_estimate_bar`) with their `indicator_provenance` label (`heuristic`, `specification_derived`) | Display names and one-line explanations for each indicator key? |
| 6 | Stage panel, upstream | `FROM UPSTREAM STAGES` with raw keys (`viscosity_class`, `moisture_flag`, …) | Same: display names and units? |
| 7 | Blocked banner | `[/] <stage> is BLOCKED by a critical constraint breach.` and the breach `message` from Role 1 (e.g. HC-001 text) | Are the HC messages final operator-facing text? |
| 8 | Override panel | `Continuing records an override. The final result will be shown as NOT RELEASABLE.` | OK? |
| 9 | Parameter panel | `(not a recommendation knob)` for `actionable: false` setpoints (cycle time, ejection force proxy) | OK? |
| 10 | Parameter panel | Display names, units and windows come straight from `constraints.yaml` (`display_name`, `unit`, `min`/`max`/`step`) | Please check them in `docs/screenshots/02-run-setup.jpg` |
| 11 | Footer, disclaimers | `DISCLAIMER_SIMULATION`, `DISCLAIMER_SHAP`, `DISCLAIMER_RECOMMENDATION`, `STATEMENT_SYNTHETIC_DATA` in `frontend/src/lib/disclaimers.ts` | Confirm the four texts, especially whether "synthetic data" still applies to `fusion-1.0.0` |
