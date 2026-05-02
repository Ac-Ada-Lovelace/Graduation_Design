# Stage-02 Execution Plan V2

This plan follows the sequence:

1. Design freeze
2. Implementation plan freeze
3. Coding
4. Verification

Current step in this file: implementation plan freeze.

## 1. Objectives

Within this cycle, deliver a runnable end-to-end demo chain:

1. Service can load an accepted model package and infer online.
2. Replay can continuously feed mains data to service.
3. UI can display latest predictions and events.
4. Integration provides one-command startup and smoke checks.

## 2. Inputs and Assumptions

1. Model package contract is stable (`nilm_model_interface_v1`).
2. Current baseline is `1s`, house_1, appliances `kettle/microwave/toaster`.
3. Accepted candidate package exists under `model/artifacts/packages/`.
4. Raw UK-DALE remains read-only.

## 3. Workstreams

### WS-A Service (P0, critical path)

Deliverables:

1. Service app with endpoints:
   - `GET /health`
   - `POST /session/start`
   - `POST /session/reset`
   - `POST /session/ingest`
   - `GET /session/latest`
2. Session state manager:
   - active package runtime
   - rolling mains buffer
   - latest prediction snapshot
3. Runtime adapter using model package loader.

Definition of done:

1. Start session with package zip path succeeds.
2. After ingesting `window_size` points, latest contains predictions.
3. Service runs stable for 10-minute replay smoke without crash.

### WS-B Replay (P1)

Deliverables:

1. CLI replay script that streams CSV rows to ingest endpoint.
2. Configurable speed multiplier.
3. Optional interval slicing for showcase windows.

Definition of done:

1. Replay sends data continuously and reports progress.
2. Service latest timestamp advances during replay.

### WS-C UI (P1)

Deliverables:

1. Minimal page showing:
   - current predicted power by appliance
   - recent event list
   - short trend chart (optional first pass)
2. Polling client for latest endpoint.

Definition of done:

1. UI refreshes every polling tick.
2. Values/events visibly change during replay.

### WS-D Integration (P2)

Deliverables:

1. Startup script for service + replay + UI.
2. Smoke script:
   - endpoint checks
   - non-empty prediction checks
3. Final runbook with exact commands.

Definition of done:

1. One command starts end-to-end demo.
2. Smoke check passes twice back-to-back.

## 4. Recommended Coding Order

1. WS-A Service core first.
2. WS-B Replay second.
3. WS-C UI third.
4. WS-D Integration last.

Reason: service is hard dependency for all downstream modules.

## 5. Timebox (Today, 3-5h target)

1. Service core: 90-120 min
2. Replay script: 45-60 min
3. Minimal UI: 45-60 min
4. Integration + smoke + docs: 45-60 min

## 6. Verification Plan

Functional checks:

1. Package loading and compatibility validation.
2. Ingest until buffer-ready and verify first prediction appears.
3. Replay continuous ingest for at least 10 minutes.
4. UI reflects live latest output.

Quality checks:

1. Basic error handling on invalid ingest payloads.
2. Endpoint latency sanity in local run.
3. Log includes model version and current session status.

## 7. Risk and Mitigation

1. ONNX runtime provider mismatch:
   - keep CPU provider default.
2. Event spam/noise:
   - use postprocess thresholds and min_on/min_off from package.
3. Interface drift:
   - fail fast on interface version or manifest mismatch.
4. Doc drift:
   - maintain one baseline source in `SYSTEM_DESIGN_V2.md`.

## 8. Exit Criteria for This Cycle

1. End-to-end demo runs with one accepted package.
2. System can switch package and continue without code changes.
3. Runbook is sufficient for repeat demo by another person.

## 9. Immediate Next Step

Start coding WS-A Service core exactly against this plan.
