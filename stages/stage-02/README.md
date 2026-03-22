# Stage 02 - NILM Online Inference Demo

Stage 02 is organized by modules. Current completed work is in `model/`.

## Core docs

- `SPEC.md`
- `EXECUTION_PLAN.md`
- `本周汇报可执行计划_nilm推理演示.md`

## Modules

- `model/`: training, export, artifact contract
- `service/`: online inference service
- `replay/`: pseudo-realtime data feeder
- `ui/`: visualization demo
- `integration/`: end-to-end scripts and runbooks

## Model-side docs

- `model/REMOTE_TRAINING_RUNBOOK.md`
- `model/docs/model_artifact_contract.md`
- `integration/ARTIFACT_ACCEPTANCE_CHECKLIST.md`

## Model Quick Start (spec-only machine)

```bash
cd model
python scripts/init_stage2.py
python scripts/window_sweep.py --config configs/default.json
python scripts/artifact_example.py --out artifacts/demo_bundle
```
