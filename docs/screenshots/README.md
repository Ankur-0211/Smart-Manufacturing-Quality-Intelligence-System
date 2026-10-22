# Process Control screenshots (R2-P6 handoff)

Captured on 2026-10-22 with the **demo profile** (`SMQI_ENV=demo`, real intelligence: Role 1's `fusion-1.0.0`, `constraints-1.0.0`).

**Setup**
- Mode: stepwise, presentation speed: instant.
- Machine and product: MC-02 / PP-JBOX-42.
- Lot: E-200, created in shot 03.
- Recipe: the registry nominal, except melt 290 °C in shots 07–08.

**Reproducing:** every value comes from the live API, so the same steps give the same frames.

**Browser:** the in-app browser pane at 731 px wide, single-column layout.

| File | Shows |
|---|---|
| `01-ready-to-run.jpg` | Context chosen, stepwise/instant mode, all six stages PENDING `[ ]`, RUN enabled |
| `02-run-setup.jpg` | Run setup: machine / product / lot pickers, sliders + inputs with windows and units from `GET /constraints`, grouped by stage |
| `03-create-lot.jpg` | "Create material lot" dialog (validated by the API against the registry) |
| `04-stepwise-mid-run.jpg` | Live over SSE after two steps: Material and Thermal completed `[X]`; stage panel with inputs in scope and upstream values |
| `05-completed-stage-detail.jpg` | All stages completed, QUALITY `P 0.24` PASS; Injection detail with derived indicators and provenance labels |
| `06-result-card.jpg` | Result card: three separate blocks (calibrated P(fail) + label + threshold + model, operational risk, anomaly status) and risk origin |
| `07-blocked-override.jpg` | Melt 290 °C above the PP-H ceiling: Thermal BLOCKED `[/]` (HC-001), override panel requiring an acknowledgement |
| `08-not-releasable.jpg` | After the override: Thermal CRITICAL "overridden", QUALITY "NOT REL.", **NOT RELEASABLE** banner over the model output (UD-07) |

**Recommendations and what-if**, on finished run `faf0cacf` (melt 290 °C, model FAIL 0.53):

| File | Shows |
|---|---|
| `09-recommendation-card.jpg` | Role 1's option (P(fail) 0.53 → 0.24), its guard checks as reported, stability/cost, and Role 2's warning that the steps exceed the registry's `max_step_change` (CCR-004 #7b) |
| `10-whatif-diff.jpg` | The same option sent to What-If and evaluated: P(fail) 0.53 → 0.24 FLIPPED, operational risk CRITICAL → LOW, parameter table incl. the cycle-time rule (UD-09) |

**Explainability**, on the same run `faf0cacf`:

| File | Shows |
|---|---|
| `11-explainability-shap.jpg` | Prediction summary, caveat banner (CRITICAL_CONSTRAINT_OVERRIDDEN), signed SHAP bars and table: melt +1.50 toward FAIL |
| `12-explainability-stage-mass.jpg` | Stage risk mass donut (Plasticizing 93 %), share list, method note and the permanent SHAP disclaimer |

**R2-P7 P1 screens**, on the same demo database:

| File | Shows |
|---|---|
| `13-whatif-live.jpg` | Live mode on run `faf0cacf`: melt 290 → 235 °C, one `persist=false` request after the pause; P(fail) 0.53 → 0.24 FLIPPED, Thermal onward recomputed |
| `14-sensitivity-strip.jpg` | Melt temperature sweep with current, flip and threshold markers, and the parameter ranking by range swing. Role 1's flip point is the first crossing (190 °C), not the nearest one (CCR-004 #7c) |
| `15-ab-compare.jpg` | A/B compare of two seeded runs (melt above ceiling vs short cooling): FAIL 0.53 → PASS 0.29, CRITICAL → LOW |
| `16-model-info.jpg` | Model Info: no metrics or calibration reported by `fusion-1.0.0` (CCR-004 #7d), global mean \|SHAP\| importance |

**R2-P8 History and Analytics**, on the same demo database (two extra scenarios saved through `POST /whatif` for the lineage):

| File | Shows |
|---|---|
| `17-lineage-tree.jpg` | Run detail of a grandchild scenario: the tree from the root run with its children, this run highlighted, "Compare with parent" links |
| `18-analytics-totals.jpg` | Stated exclusions (3 what-if, 0 mock, 1 unfinished) and totals: 6 runs, predicted FAIL share 33 %, 2 NOT RELEASABLE, few-runs caution |
| `19-analytics-by-parameter.jpg` | Melt temperature in five registry-window buckets: both predicted FAILs are in 272–295 °C |
| `20-analytics-spc.jpg` | Melt temperature series on MC-02 without control limits, and why (CCR-004 #10) |

**Note:** the risk origin is split evenly at 20 % per stage. That is Role 1's `stage_risk_mass` for this input; see CCR-004 #3.
