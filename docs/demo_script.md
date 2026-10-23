# Demo script (8 minutes) — roadmap R2-P10 task 7, §16.4

Every number below comes from the deterministic demo history (`scripts/seed_demo_runs.py`) on Role
1's `fusion-1.0.0` and `constraints-1.0.0`. The E2E spec `frontend/e2e/demo.spec.ts` replays the
script's steps and fails if any of these numbers changes. Re-run it after every Role 1 update, and
edit this script if it fails.

## Before the audience arrives (T − 15 min)

1. Build once: `cd frontend && npm run build`.
2. Start a clean demo database, then the API in the demo profile (`docs/deployment.md`):
   ```bash
   uv run alembic -c backend/alembic.ini upgrade head
   uv run python -m app.db.seed
   SMQI_ENV=demo SMQI_INTELLIGENCE_BACKEND=real uv run uvicorn app.main:app --app-dir backend --port 8000
   ```
3. Second terminal: `uv run python scripts/seed_demo_runs.py`. It prints four runs; note the run ids of **high injection pressure** and **melt above ceiling**.
4. Open <http://localhost:8000/> full screen in one browser window. Check:
   - the header shows `API: ok`;
   - there is no MOCK banner;
   - Model Info says `fusion-1.0.0`, intelligence `real`.
5. Keep the backup video (task 8) open in a second window, paused at 0:00.

## The 8 minutes

| Time | Segment | Who | Do | Say / point at |
|---|---|---|---|---|
| 0:00 | Problem and claims | R1 | (slides) | PP injection molding of a 42 g junction box. Four claims: software-level simulation, statistical prediction, associations not causes, model-relative recommendations |
| 0:45 | Context and validation | R2 | Process Control → Machine **MC-02**, Product **PP-JBOX-42**, Lot **A-771** → *Load nominal recipe*. Type **400** into Melt Temperature | Sliders, windows and units come from the constraint registry; 400 °C shows "Allowed 180–295 °C" and RUN is disabled. Set it back to **230** |
| 1:30 | Live run with an anomaly | R2 | Set Injection Pressure to **1800**, Mode auto, speed **1x**, RUN | Stages turn on one by one over SSE (`live (SSE)`). **Injection / Fill** shows the anomaly marker. Timeline on the right |
| 2:30 | Result and risk separation | R2 | Point at the result card | Three separate blocks: model-predicted P(fail) **0.59 (calibrated)**, Prediction **FAIL** at threshold 0.35; operational risk **HIGH**; anomaly status. Risk origin: **Injection 86 %** |
| 3:00 | Why | R1 | *Why this prediction?* | SHAP bars: **Injection Pressure +0.80 toward FAIL** at the top; stage risk mass donut dominated by Injection; the association-not-causation disclaimer |
| 3:45 | What should I change | R1 | *What should I change?* → *Find options* | Option cards with the guard stamp, stability 0/20 flips, cycle-time cost and the permanent disclaimer. **Be honest:** today's options predict no gain (0.59 → 0.59) and the step-limit warning is visible. Both are open with Role 1 (CCR-004 #7a, #7b) |
| 4:45 | What-if flip | R2 | *Try a what-if* → Injection Pressure **1100** → *Evaluate* | P(fail) **0.59 → 0.24, FLIPPED** to PASS; operational risk **HIGH → LOW**. Stages: **Material and Thermal reused**, Injection, Packing and Cooling recomputed. Then set Injection Pressure back and change only Cooling Time to **12**: only **Cooling** is recomputed. Save as scenario "demo: what-if 1100 bar" |
| 5:45 | BLOCKED | R2 | History → open **demo: melt above ceiling** → *Open in Process Control* | Thermal is **BLOCKED** by HC-001 (290 °C above the PP-H ceiling). Type an acknowledgement → *Override and continue*, then press **STEP** for each remaining stage (the seeded run is stepwise, so each stage is shown). Result: **NOT RELEASABLE**, risk CRITICAL, caveat `CRITICAL_CONSTRAINT_OVERRIDDEN` |
| 6:30 | History, analytics, Model Info | R2 / R1 | History → the high-injection run → lineage tree shows the saved what-if. Analytics. Model Info | Analytics excludes what-if scenarios by default and says so. By parameter shows where the predicted FAILs sit. Model Info shows the synthetic-data statement; metrics are "not reported" by the current model (CCR-004 #7d) |
| 7:15 | Evaluation and limitations | R1 | (slides) | Evaluation highlights, then the limitations: the four claims, synthetic data, no SPC alerts yet, model-relative options |

## Failure recovery

| Symptom | Recovery |
|---|---|
| Stages don't animate (SSE blocked by the network) | Nothing to do: the view switches to polling (`live (polling)`) and finishes. Or rerun in **stepwise** mode and press STEP |
| 1x is too slow for the remaining time | Set the presentation speed to **instant**, or open the seeded high-injection-pressure run from History |
| API down or browser crashes | Restart the API (step 2 above, without re-seeding); the database keeps the seeded runs. A run that was executing comes back as ABORTED and stays inspectable |
| Anything else | Switch to the backup video at the segment's timestamp |

## Deviations from the roadmap plan (§16.4)

| Planned | Today | Why |
|---|---|---|
| Context MC-03 | **MC-02** | MC-03's 110 t clamp is below the nominal 120 t (CPL-003; CCR-004 #7) |
| Anomaly badge on Thermal | Anomaly on **Injection** | That is where Role 1's facade flags it for this recipe |
| Recommendations flip the verdict | Options predict no gain; the flip is a manual what-if | CCR-004 #7a |
| Model Info metrics | "not reported" | CCR-004 #7d |

Update this table, and the timings, after the rehearsal and after each Role 1 release.
