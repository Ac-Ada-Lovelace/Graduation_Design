# Stage-02 System Design (v1)

This document defines the executable architecture for the Stage-02 NILM demo.
It is written to keep model work, service work, and demo integration aligned.

## 1. Scope

Stage-02 target: deliver a deployable NILM inference capability and a stable demo loop.

Included modules:

- `model/`: dataset prep, training, export, acceptance.
- `service/`: online inference session and API.
- `replay/`: pseudo-realtime mains data feeder.
- `ui/`: charts for mains / truth / prediction / events.
- `integration/`: end-to-end startup and acceptance runbook.

## 2. Design Goals

1. Deterministic model package interface (hot-swap capable).
2. Raw dataset remains read-only; all processing is in copied outputs.
3. Reproducible training and acceptance reports.
4. Online session can run continuously and expose latest predictions/events.

## 3. End-to-End Architecture

```text
UK-DALE raw (read-only)
  -> model/data/processed/*
  -> train_seq2point.py
  -> artifacts/models/<artifact_id>/*
  -> export_model_package.py
  -> artifacts/packages/<artifact_id>__<profile>.zip
  -> service runtime (package loader + ONNX session)
  -> replay ingest loop
  -> session latest output
  -> UI visualization
```

## 4. Cross-Module Contract

The model package zip is the only required boundary between training and service.

Required files:

1. `model.onnx`
2. `model_meta.json`
3. `normalization.json`
4. `postprocess.json`
5. `interface_spec.json`
6. `package_manifest.json`

Contract reference:

- `model/docs/model_artifact_contract.md`

Runtime reference:

- `model/src/nilm_stage2/package_runtime.py`

Acceptance reference:

- `model/scripts/run_stage02_acceptance.py`

## 5. Runtime Data Flow (Service Perspective)

1. `POST /session/start` loads a package zip and initializes session state.
2. `POST /session/ingest` appends one mains sample to rolling buffer.
3. Once rolling buffer length reaches `window_size`, service performs one ONNX inference.
4. Service denormalizes prediction and applies optional linear calibration.
5. Service extracts events using threshold + hysteresis + min duration.
6. `GET /session/latest` returns timestamp, per-device predicted watts, events, and model version.

## 6. Acceptance Gate

A candidate package is accepted only when all checks pass:

1. Contract completeness: all required files + required keys.
2. Interface compatibility: `interface_version == nilm_model_interface_v1`.
3. Manifest validation: file bytes and SHA256 match.
4. Fixed-interval metrics generated:
   - numeric error: MAE/RMSE
   - event quality: event F1 under configured tolerance.

## 7. Versioning and Rollback

Package identity:

- `<artifact_id>__<profile>.zip`

Publish policy:

1. Keep at least one previous accepted package as rollback target.
2. Store acceptance report with package release note.
3. Rollback means changing package pointer only; no code rollback required.

## 8. Non-Functional Constraints

1. Data integrity: never modify `model/data/raw/uk-dale/*`.
2. Observability: keep run reports in `model/runs/*`.
3. Reproducibility: preserve config, seed, and artifact metadata.
4. Portability: default runtime provider is CPU unless deployment explicitly enables GPU.

## 9. Implementation Backlog (Next)

1. Service: implement package-driven session API and latest-state response contract.
2. Replay: stream selected showcase interval at near-realtime pace to service ingest.
3. UI: align plotting schema with service latest response.
4. Integration: one-command local demo start + smoke check.
