# Stage 02 / Model

Model training and export module.

## Docs

- `REMOTE_TRAINING_RUNBOOK.md`
- `docs/model_artifact_contract.md`

## Notes

- 本机可编写规范与脚本，不承担实际训练。
- 训练在远程训练机执行，工件回传到 `artifacts/`。

## Data Preparation (read-only raw data)

Raw UK-DALE files under `data/raw/uk-dale` are treated as read-only.
Prepared datasets are written to `data/processed/...` so raw files stay unchanged.

Example (house_1, 1s alignment, 7 days):

```bash
python scripts/prepare_house1_timeseries.py --config configs/default.json --duration-hours 168
```

Outputs:

- `data/processed/house_1_1s/timeseries_1s_full.csv`
- `data/processed/house_1_1s/timeseries_1s_train_ready.csv`
- `data/processed/house_1_1s/quality_report.json`

## Train (GPU/CPU)

Example (single run, default window from config):

```bash
python scripts/train_seq2point.py --config configs/default.json
```

Window sweep command generation:

```bash
python scripts/window_sweep.py --config configs/default.json
```

Quick smoke run (fast check):

```bash
python scripts/train_seq2point.py --config configs/default.json --epochs 1 --max-train-samples 5000 --max-val-samples 1000 --max-test-samples 1000
```

Balanced 9-run plan (3+3+3 with early stop):

```bash
python scripts/run_balanced_training_plan.py --config configs/default.json --device cuda --num-workers 0
```

## Added in this iteration

- `docs/model_system_design.md`
- `docs/stage02_deploy_acceptance.md`
