# Stage-02 Deploy and Acceptance

This page records the runnable deployment/acceptance mainline for Stage-02.

## 1) Export package zip

Event-optimized package:

```bash
python scripts/export_model_package.py ^
  --artifact-id kmt_multi_w301_20260323_155405_thopt_20260323_161139 ^
  --profile event_optimized ^
  --include-reports
```

Error-optimized package:

```bash
python scripts/export_model_package.py ^
  --artifact-id kmt_multi_w301_20260323_155405_calibrated_20260323_161136 ^
  --profile error_optimized ^
  --include-reports
```

Generated files live under `artifacts/packages/`.

## 2) Run fixed-interval acceptance

Event package:

```bash
python scripts/run_stage02_acceptance.py ^
  --package-zip artifacts/packages/kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip ^
  --data-csv data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --intervals-json configs/stage02_acceptance_intervals_kmt.json ^
  --event-tolerance-s 10
```

Acceptance reports are written to `runs/acceptance_<timestamp>/`.

## 3) Interface contract

- Contract doc: `docs/model_artifact_contract.md`
- Interface version: `nilm_model_interface_v1`
- Runtime loader: `src/nilm_stage2/package_runtime.py`
