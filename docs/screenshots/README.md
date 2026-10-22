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

**Note:** the risk origin is split evenly at 20 % per stage. That is Role 1's `stage_risk_mass` for this input; see CCR-004 #3.
