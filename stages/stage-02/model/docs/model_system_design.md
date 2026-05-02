# Stage-02 Model System Design (v1)

This document defines the model-side architecture from data preparation to
deployable package runtime.

## 1. Model-Side Objectives

1. Train on aligned 1-second data with reproducible configs.
2. Export one self-contained package zip as deployment unit.
3. Keep package interface stable so service can swap models without code changes.
4. Produce acceptance reports that are easy to compare across artifacts.

## 2. Directory Responsibilities

- `data/raw/uk-dale/`: read-only dataset source.
- `data/processed/...`: prepared training/evaluation copies.
- `scripts/prepare_house1_timeseries.py`: build processed datasets.
- `scripts/train_seq2point.py`: train multi-output seq2point model.
- `artifacts/models/<artifact_id>/`: training artifact directory.
- `scripts/export_model_package.py`: convert artifact to package zip.
- `artifacts/packages/*.zip`: deployment-ready packages.
- `src/nilm_stage2/package_runtime.py`: standardized package loader/runtime.
- `scripts/run_stage02_acceptance.py`: fixed-interval acceptance runner.

## 3. Data and Tensor Contracts

Data assumptions:

1. `sample_period_s = 1` for current Stage-02 mainline.
2. Main input column is `mains_w`.
3. Appliance targets are ordered and consistent across meta/norm/postprocess.

Tensor contract:

- Input: `float32 [batch, window_size, 1]`
- Output: `float32 [batch, num_appliances]`

Contract source of truth:

- `docs/model_artifact_contract.md`

## 4. Build Pipeline

1. Prepare processed data copy from raw UK-DALE.
2. Train and evaluate candidate model artifacts.
3. Select artifact profile (`event_optimized` or `error_optimized`).
4. Export package zip with interface and manifest files.
5. Run fixed-interval acceptance and store report in `runs/acceptance_*`.

## 5. Package Runtime Design

`ModelPackageRuntime` is the deployment adapter.

Responsibilities:

1. Validate required files and interface version.
2. Validate manifest hash/size consistency.
3. Create ONNX runtime session.
4. Provide preprocessing and denormalization utilities.
5. Provide optional linear calibration hook.
6. Provide event extraction and event F1 evaluation utilities.

Public inference entrypoints:

1. `infer_windows_watts(...)`
2. `infer_windows_watts_batched(...)`

## 6. Event Logic Design

Event pipeline per appliance:

1. Hysteresis state generation (`on_threshold_w`, `off_threshold_w`).
2. Minimum on/off duration enforcement.
3. State-change to event conversion (`on`/`off`).
4. Tolerance-based event matching for F1 metric.

Main reason: reduce false toggles while preserving timing utility for demo.

## 7. Acceptance Design

Acceptance script behavior:

1. Load package zip via runtime loader.
2. Load evaluation CSV and align sliding windows.
3. Evaluate pre-defined fixed time intervals from JSON config.
4. Emit both `report.json` and `report.md`.

Aggregate metrics:

1. MAE average across appliances and intervals.
2. RMSE average across appliances and intervals.
3. Event F1 average across appliances and intervals.

## 8. Swap and Compatibility Policy

A new package is swappable only if:

1. `interface_spec.interface_version` matches expected interface.
2. `sample_period_s` is compatible with caller expectation.
3. Tensor names/ranks are compatible.
4. Appliance order is accepted by downstream consumers.

If any condition fails, package loading must fail fast.

## 9. Failure Modes and Guards

1. Missing package fields: guarded by required-key validation.
2. Drift between files: guarded by manifest hash+size checks.
3. Input shape mismatch: guarded by runtime shape checks.
4. Raw data contamination: guarded by read-only policy for raw directory.
5. Provider mismatch (GPU dll): mitigated by CPU provider default.

## 10. Next Engineering Steps

1. Define service request/response JSON schema aligned to package runtime output.
2. Add a lightweight package registry index (accepted candidates + metrics).
3. Add CI-style contract validation script for package zips.
4. Add one golden interval regression check for each accepted package.
