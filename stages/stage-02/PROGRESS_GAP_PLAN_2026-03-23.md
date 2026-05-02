# Stage-02 Progress, Gap, and Next Plan (2026-03-23)

This page expands the system design into execution checkpoints.

## 1. Target Shape in Final System

The model-side work should be consumed as a plugin-like deployment unit:

1. Model training outputs one package zip.
2. Service loads package zip and runs online inference.
3. Replay continuously feeds mains power samples to service.
4. UI reads service latest state and renders mains/true/pred/events.
5. Integration scripts run one-command demo and smoke validation.

## 2. Current Snapshot (as of 2026-03-23)

### Model package and acceptance

Available package zips:

1. `kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip`
2. `kmt_multi_w301_20260323_155405_calibrated_20260323_161136__error_optimized.zip`

Latest fixed-interval acceptance (event-optimized):

- MAE avg: `11.2317 W`
- RMSE avg: `44.7314 W`
- Event F1 avg: `1.0000`

### Module implementation status

1. `model/`: implemented and runnable.
2. `service/`: README only, no runtime API implementation yet.
3. `replay/`: README only, no feeder implementation yet.
4. `ui/`: README only, no visualization implementation yet.
5. `integration/`: checklist/readme present, no one-command runner yet.

## 3. Progress Matrix

1. Model training/export/acceptance: ~85%
2. Service online inference API: ~5%
3. Replay feeder: ~0%
4. UI demo page: ~0%
5. End-to-end integration automation: ~10%

Overall Stage-02 delivery progress: ~30-35%

## 4. Main Gaps

1. Missing service API that actually consumes exported package zip.
2. No rolling-window online inference session lifecycle.
3. No replay-to-service data path.
4. No UI linked to live service outputs.
5. No single command to run the full demo chain.
6. Decision drift in old docs:
   - old snapshot mentions `6s + kettle/microwave/fridge`
   - current mainline is `1s + kettle/microwave/toaster`
   - this must be unified in one source-of-truth doc before final demo.

## 5. Next Plan (Execution Order)

## Phase P0 (today, highest priority)

Goal: make model work usable by final system.

Tasks:

1. Implement service API skeleton:
   - `GET /health`
   - `POST /session/start` (load package zip)
   - `POST /session/reset`
   - `POST /session/ingest` (rolling buffer + inference)
   - `GET /session/latest`
2. Reuse `ModelPackageRuntime` from `model/src/nilm_stage2/package_runtime.py`.
3. Return JSON fields: timestamp, pred_w per appliance, events, model_version.

Done criteria:

1. Can start session with selected package zip.
2. Can ingest >= `window_size` points and receive prediction output.
3. Can keep running for at least 10 minutes without crash in local smoke test.

## Phase P1 (after P0)

Goal: close data loop and make demo executable.

Tasks:

1. Implement replay script to stream prepared CSV at near-realtime pace.
2. Implement minimal UI page:
   - latest predicted power per appliance
   - latest event list
   - optional lightweight trend chart
3. Add integration startup script:
   - start service
   - start replay
   - open UI or print endpoints

Done criteria:

1. End-to-end loop runs with one command.
2. UI/console shows changing predictions and events during replay.

## Phase P2 (stability and presentation)

Goal: make final handoff and demo rehearsal stable.

Tasks:

1. Package registry file for accepted model package pointer.
2. Add rollback command to switch package pointer.
3. Add final runbook with exact commands and expected outputs.
4. Update conflicting docs to a single final baseline.

Done criteria:

1. Switch between two packages without code change.
2. Full demo replay passes smoke check twice in a row.

## 6. Immediate Decision Needed

Choose service implementation stack for P0:

1. FastAPI (recommended for rapid API + docs).
2. Flask (lighter, fewer dependencies).

Without this choice, P0 coding can still start with FastAPI default.

## 7. Implementation Update (same day)

Completed in coding round:

1. Service API implemented with package runtime integration.
2. Replay feeder implemented.
3. Minimal UI implemented.
4. Integration smoke and live launcher implemented.
5. Package registry and active-package switching implemented.

Updated progress estimate:

1. Model training/export/acceptance: ~90%
2. Service online inference API: ~80%
3. Replay feeder: ~85%
4. UI demo: ~70%
5. End-to-end integration automation: ~80%

Updated overall Stage-02 delivery progress: ~80-85%

Remaining key gaps:

1. Add stronger endpoint tests and schema validation tests.
2. Add a final rehearsal runbook with expected screenshots/outputs.
3. Resolve historical doc drift into one final baseline page.
