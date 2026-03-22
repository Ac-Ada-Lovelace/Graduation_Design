# Stage 02 - NILM Inference Service (Model-Export First)

This stage focuses on one hard target:
train usable NILM models and export deployable inference artifacts.

## Scope (This Week)

- Dataset: UK-DALE (prefer 1s demo pipeline; allow resampling fallback)
- Appliances: kettle, microwave, fridge
- Model family: Seq2Point
- Service mode: single-user online inference

## Hard Deliverables

1. Trained model checkpoints for at least 2-3 appliances
2. Exported inference artifacts (ONNX + metadata)
3. A local inference runner that loads exported artifacts
4. Single-user inference service API wired to real model outputs
5. Replay demo that continuously feeds mains and displays predictions

## Quick Start

```bash
python scripts/init_stage2.py
python scripts/window_sweep.py --config configs/default.json
python scripts/artifact_example.py --out artifacts/demo_bundle
```

## Recommended Next Tasks

1. Fill UK-DALE path and selected house in `configs/default.json`
2. Implement `scripts/train_seq2point.py` with `--window-size` override
3. Implement `scripts/export_onnx.py` using `src/nilm_stage2/artifact.py`
4. Implement inference service and replay script on top of fixed artifact contract

## Minimal Research Still Needed

1. Confirm selected UK-DALE house has all three target appliances in chosen period
2. Confirm effective missing-rate after alignment/resample
3. Confirm 1s demo segment duration is long enough (recommend >= 20 minutes)

