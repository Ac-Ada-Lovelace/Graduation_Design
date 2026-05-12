# Stage-02 Acceptance Report

- Package: `kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip`
- Interface: `nilm_model_interface_v1`
- Appliances: `['kettle', 'microwave', 'toaster']`

## Aggregate

- MAE avg (interval mean): `11.2317 W`
- RMSE avg (interval mean): `44.7314 W`
- Event F1 avg (interval mean): `1.0000`

## Intervals

| id | minutes | rows | mae_avg_w | rmse_avg_w | event_f1_avg |
|---|---:|---:|---:|---:|---:|
| kmt_15m_a | 15 | 900 | 14.3422 | 52.1361 | 1.0000 |
| kmt_20m_a | 20 | 1200 | 11.2319 | 45.1631 | 1.0000 |
| kmt_30m_a | 30 | 1800 | 8.1210 | 36.8951 | 1.0000 |
