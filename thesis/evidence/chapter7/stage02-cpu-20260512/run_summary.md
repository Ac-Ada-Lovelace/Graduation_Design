# Stage-02 CPU 复现实验摘要

日期：2026-05-12

## 1. 环境与输入

| 项目 | 内容 |
| --- | --- |
| 分支 | `codex/chapter5-model-package-requirements` |
| 模型包 | `stages/stage-02/model/artifacts/packages/kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip` |
| 推理数据 | `stages/stage-02/model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv` |
| 目标设备 | `kettle`、`microwave`、`toaster` |
| 模型接口 | `nilm_model_interface_v1` |
| 推理环境 | Windows 本机 CPU，ONNX Runtime CPUExecutionProvider |

## 2. 命令与输出文件

| 检查项 | 命令 | 输出文件 | 结果 |
| --- | --- | --- | --- |
| active package 校验 | `python integration\manage_package_registry.py verify-active` | `verify-active.txt` | `exists=True` |
| 服务 API 检查 | `python integration\run_service_api_checks.py` | `api-check.txt` | `[api-check] PASS (session + offline + online)` |
| 在线回放 smoke | `python integration\run_demo_smoke.py --data-csv model\data\processed\house_1_1s_kmt\timeseries_1s_train_ready.csv --speed 200 --max-rows 320` | `smoke.txt` | `[smoke] PASS` |
| 离线推理样例 | FastAPI TestClient 调用 `/api/offline/infer` | `offline-infer-summary.json` | 返回指标和事件匹配结果 |
| 在线回放样例 | FastAPI TestClient 调用 `/api/online/start` 和 `/api/online/status` | `online-status-summary.json` | `sent_rows=420`，`pred_count=120` |

## 3. 关键结果

### 3.1 固定区间验收报告

| 模型包 | MAE 平均值/W | RMSE 平均值/W | Event F1 平均值 |
| --- | ---: | ---: | ---: |
| event optimized | 11.2317 | 44.7314 | 1.0000 |
| error optimized | 12.9034 | 62.7407 | 0.8333 |

### 3.2 在线 smoke 结果

| 字段 | 值 |
| --- | --- |
| `ready` | `true` |
| `buffer_fill` | 301 |
| `window_size` | 301 |
| `ingest_count` | 320 |
| `pred_count` | 20 |
| `model_version` | `kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip` |

### 3.3 离线推理样例结果

样例区间为 `2013-03-19T17:35:02Z` 至 `2013-03-19T18:42:14Z`。

| 指标 | 值 |
| --- | ---: |
| MAE 平均值/W | 17.5778 |
| RMSE 平均值/W | 112.3741 |
| MeanDiff 平均值/W | 7.2924 |
| MaxAbsDiff/W | 2481.4275 |
| Event F1 平均值 | 1.0000 |
| 原始对齐点数 | 3571 |
| 返回点数 | 420 |

## 4. 结论

本次验证说明，训练机器提交的 Stage-02 模型包、处理后 CSV 和验收报告可以在本机 CPU 环境下被服务加载和调用。active package 校验、服务 API 检查和在线回放 smoke 均通过，离线区间推理和在线回放接口能够返回可用于第 7 章测试分析的指标、事件和状态字段。

