# Stage-02 Final Demo Runbook

This runbook is the final operating guide for Stage-02 demo delivery.

## 1. Pre-check

From `stages/stage-02`:

```bash
python integration/manage_package_registry.py verify-active
python integration/run_service_api_checks.py
```

Expected:

1. Active package path exists.
2. API checks print `[api-check] PASS`.

## 2. Quick Smoke (Recommended Before Live Demo)

```bash
python integration/run_demo_smoke.py ^
  --data-csv model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --speed 200 ^
  --max-rows 320
```

Expected:

1. `[smoke] service is healthy`
2. `[smoke] latest ready=True pred_count>0`
3. `[smoke] PASS`

## 3. Live Demo Start

```bash
python integration/run_demo_live.py ^
  --service-port 18080 ^
  --ui-port 3000
```

Expected:

1. Console prints `UI URL`.
2. Open UI URL and use two tabs:
   - `离线展示`: 选择区间 -> 启动推理 -> 查看真值/预测/事件对比
   - `在线模拟`: 选择起点和速度 -> 启动在线回放 -> 查看实时真值/预测曲线

Stop live demo with `Ctrl+C`.

## 4. Model Switch / Rollback

List available packages:

```bash
python integration/manage_package_registry.py list
```

Switch active package:

```bash
python integration/manage_package_registry.py set-active --package-id kmt_error_optimized
```

Switch back:

```bash
python integration/manage_package_registry.py set-active --package-id kmt_event_optimized
```

After switch, rerun smoke to confirm:

```bash
python integration/run_demo_smoke.py ^
  --data-csv model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --max-rows 320
```

## 5. Demo Baseline Summary

Current baseline (mainline):

1. House: `house_1`
2. Cadence: `1s`
3. Appliances: `kettle`, `microwave`, `toaster`
4. Default active package:
   `kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip`

Acceptance reference (event-optimized):

1. MAE avg: `11.2317 W`
2. RMSE avg: `44.7314 W`
3. Event F1 avg: `1.0000`

## 6. Troubleshooting

1. If `/session/start` fails:
   - verify active package path exists:
     `python integration/manage_package_registry.py verify-active`
2. If replay fails:
   - check service is alive:
     `curl http://127.0.0.1:18080/health`
3. If UI shows disconnected:
   - confirm service port and `?service=...` URL parameter
4. If runtime provider warnings appear:
   - keep CPU provider default (current config already does this)
