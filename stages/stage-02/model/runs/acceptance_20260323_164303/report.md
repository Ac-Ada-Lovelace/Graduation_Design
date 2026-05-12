# Stage-02 Acceptance Report

- Package: `kmt_multi_w301_20260323_155405_calibrated_20260323_161136__error_optimized.zip`
- Interface: `nilm_model_interface_v1`
- Appliances: `['kettle', 'microwave', 'toaster']`

## Aggregate

- MAE avg (interval mean): `12.9034 W`
- RMSE avg (interval mean): `62.7407 W`
- Event F1 avg (interval mean): `0.8333`

## Intervals

| id | minutes | rows | mae_avg_w | rmse_avg_w | event_f1_avg |
|---|---:|---:|---:|---:|---:|
| kmt_15m_a | 15 | 900 | 17.0510 | 73.1483 | 0.8333 |
| kmt_20m_a | 20 | 1200 | 12.9036 | 63.3488 | 0.8333 |
| kmt_30m_a | 30 | 1800 | 8.7557 | 51.7248 | 0.8333 |
