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

## Added in this iteration

- `SYSTEM_DESIGN.md`
- `model/docs/model_system_design.md`
- `PROGRESS_GAP_PLAN_2026-03-23.md`
- `SYSTEM_DESIGN_V2.md`
- `EXECUTION_PLAN_V2.md`
- `integration/run_demo_smoke.py`
- `integration/package_registry.json`
- `integration/manage_package_registry.py`
- `integration/run_service_api_checks.py`
- `FINAL_DEMO_RUNBOOK.md`
- `SPEC_OFFLINE_ONLINE_EXPERIENCE.md`
- `IMPLEMENTATION_PLAN_OFFLINE_ONLINE.md`
- `SPEC_OFFLINE_ONLINE_DETAILED_V1.md`
