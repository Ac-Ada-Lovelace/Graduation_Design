# Stage-02 System Design V2

This document defines how Stage-02 model work is consumed by the final demo
system as a deployable and replaceable capability.

## 1. Goal

Build a runnable NILM demo chain with clear boundaries:

1. Model team outputs a package zip.
2. Service loads package and provides online inference APIs.
3. Replay streams mains data to service.
4. UI visualizes mains, predicted appliance power, and events.

## 2. Scope

In-scope modules:

1. `model/`
2. `service/`
3. `replay/`
4. `ui/`
5. `integration/`

Out-of-scope for Stage-02:

1. Multi-user production scaling
2. Complex model orchestration
3. Long-term online learning

## 3. Architecture

```text
UK-DALE raw (read-only)
  -> processed CSV (1s aligned)
  -> model training + export
  -> package zip (onnx + metadata + rules)
  -> service session runtime
  -> replay ingest stream
  -> session latest state
  -> UI rendering
```

## 4. Model Package Contract

Deployment unit is one zip file with required artifacts:

1. `model.onnx`
2. `model_meta.json`
3. `normalization.json`
4. `postprocess.json`
5. `interface_spec.json`
6. `package_manifest.json`

Compatibility gate:

1. `interface_version == nilm_model_interface_v1`
2. Input/output tensor schema matches runtime adapter
3. `sample_period_s` accepted by service
4. Appliance order accepted by downstream consumers

## 5. Service Design

Service responsibilities:

1. Load package zip into one active session.
2. Maintain rolling mains buffer.
3. Trigger inference when buffer reaches `window_size`.
4. Apply denorm + optional linear calibration + event extraction.
5. Return latest state to consumers.

MVP API set:

1. `GET /health`
2. `POST /session/start`
3. `POST /session/reset`
4. `POST /session/ingest`
5. `GET /session/latest`

Suggested latest response schema:

```json
{
  "timestamp_utc": "2013-03-24T08:00:24Z",
  "pred_w": {
    "kettle": 0.0,
    "microwave": 0.0,
    "toaster": 781.2
  },
  "events": [
    {"device": "toaster", "type": "on", "index": 1234}
  ],
  "model_version": "kmt_multi_w301_...__event_optimized.zip",
  "buffer_fill": 301
}
```

## 6. Replay Design

Replay responsibilities:

1. Read prepared CSV rows in time order.
2. Push one sample per configured tick (default 1 second pace, optional speed-up).
3. Send to `POST /session/ingest`.
4. Log ingestion progress and error retries.

Replay minimal CLI args:

1. `--data-csv`
2. `--service-base-url`
3. `--speed`
4. `--start-ts` and `--end-ts` (optional interval demo window)

## 7. UI Design

UI responsibilities:

1. Poll `GET /session/latest`.
2. Render per-appliance predicted watts.
3. Render event timeline (ON/OFF markers).
4. Optionally render mains/true/pred trend in short moving window.

UI can start as minimal single page; styling is not priority for first pass.

## 8. Integration Design

Integration responsibilities:

1. One command to launch service, replay, and UI.
2. Smoke checks for key endpoints and live updates.
3. Document expected outputs and fallback commands.

## 9. Release and Rollback

Release flow:

1. Train/export candidate package
2. Run fixed-interval acceptance
3. Mark one package as active
4. Start service with active package

Rollback flow:

1. Switch active package pointer to previous accepted package
2. Restart service session

No service code changes should be required for model switch.

## 10. Observability

Required runtime visibility:

1. Ingest count and effective sample rate
2. Inference latency p50/p95
3. Last prediction timestamp and staleness
4. Event counts per device
5. Session/model version metadata

## 11. Data Governance

1. `model/data/raw/uk-dale/` remains read-only.
2. All generated data goes to `model/data/processed/` or `model/runs/`.
3. Acceptance reports are immutable release evidence.

## 12. Baseline Alignment (Current Mainline)

Current baseline for Stage-02 mainline:

1. Data cadence: `1s`
2. House: `house_1`
3. Appliances: `kettle`, `microwave`, `toaster`
4. Acceptance: fixed intervals + MAE/RMSE/Event F1

Any doc mentioning `6s` or `fridge` for the mainline should be treated as
historical context unless explicitly re-approved.
