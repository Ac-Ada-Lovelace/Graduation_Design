# Stage-02 Implementation Plan (Offline + Online Experience)

## 1. Scope

Deliver a complete demo loop that supports:

1. Offline interval evaluation view.
2. Online replay simulation view.
3. Model package switch via registry without code change.

## 2. Work Breakdown

### P0 Architecture and API

1. Define spec for dual-mode experience.
2. Extend backend API for metadata/offline/online flows.
3. Keep compatibility with existing session endpoints.

Done:

1. `/api/meta`, `/api/offline/infer`, `/api/online/start|stop|status` available.
2. Basic API checks pass.

### P1 Frontend Dual-Mode Console

1. Build UI tabs:
   - offline controls and charts
   - online controls and live charts
2. Wire to backend APIs.
3. Add runtime error display and status badges.

Done:

1. User can run offline interval inference from UI.
2. User can start/stop online replay from UI.

### P2 Integration and Runbook

1. Update service/replay/integration docs.
2. Keep smoke and live launch scripts compatible.
3. Add final runbook commands for rehearsal.

Done:

1. `run_service_api_checks.py` passes.
2. `run_demo_smoke.py` passes.
3. Live page can be opened and controlled.

## 3. Verification Checklist

1. Health and meta APIs return expected fields.
2. Offline infer returns:
   - non-empty series
   - MAE/RMSE and event metrics
3. Online replay:
   - start accepted
   - sent_rows increases
   - latest.pred_count increases after buffer ready
4. UI:
   - offline chart renders true/pred curves
   - online chart updates while replay runs

## 4. Risks and Mitigations

1. Cross-origin fetch blocked:
   - enable CORS in service.
2. Large interval payload:
   - enforce `max_points`.
3. Replay concurrency conflicts:
   - reject duplicate online start while running.
4. Environment process exits:
   - keep smoke script as quick validation fallback.
