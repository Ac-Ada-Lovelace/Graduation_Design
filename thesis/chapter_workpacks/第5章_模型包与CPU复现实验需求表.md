# 第5章模型包与CPU复现实验需求表

日期：2026-05-12

## 1. 目标

本表用于向 GPU 训练机器收集 Stage-02 NILM 模型复现实验所需文件。当前目标是在本机使用 CPU 执行 ONNX 推理，完成模型包校验、离线区间推理、在线回放 smoke 和论文第 7 章可引用的测试记录。

## 2. 优先交付清单

| 优先级 | 需求项 | 是否必须 | 推荐格式 | 放置位置 | 用途 | 校验方式 |
| --- | --- | --- | --- | --- | --- | --- |
| P0 | 标准模型包 | 必须 | `.zip` | `stages/stage-02/model/artifacts/packages/` 或 `stages/stage-02/artifacts/packages/` | 作为服务加载和 CPU 推理的部署单元 | `ModelPackageRuntime.load(..., validate_manifest=True)` |
| P0 | 推理/验收 CSV | 必须 | `.csv` | `stages/stage-02/model/data/processed/house_1_1s_kmt/` | 用于离线区间推理和在线回放 | 检查 `timestamp_utc`、`mains_w` 和设备功率列 |
| P0 | 模型包对应设备清单 | 必须 | 写入 `model_meta.json` 或补充说明 | 随模型包提供 | 确认输出设备顺序和论文表述一致 | 对照 `model_meta.json.appliances` |
| P1 | 固定区间验收报告 | 推荐 | `report.json`、`report.md` | `stages/stage-02/model/runs/acceptance_<timestamp>/` | 为第 7 章指标表提供原始依据 | 对照注册表指标和报告 aggregate |
| P1 | ONNX parity check | 推荐 | `onnx_parity_check.json` | 模型训练工件目录或模型包内 | 证明 ONNX 导出与训练侧推理一致 | 检查最大绝对差等字段 |
| P1 | 校准/阈值优化报告 | 可选 | `.json` | 模型训练工件目录或模型包内 | 说明误差优化或事件优化 profile 来源 | 对照 `postprocess.json` |
| P2 | 训练配置 | 可选 | `.json` 或 `.yaml` | `stages/stage-02/model/configs/` | 追溯窗口长度、采样周期、训练参数 | 对照 `model_meta.json` |
| P2 | 训练日志摘要 | 可选 | `.md` 或 `.txt` | `stages/stage-02/model/runs/` | 论文附录或实验记录备用 | 人工审查 |

## 3. 标准模型包内容要求

标准模型包 zip 内至少包含以下文件：

| 文件 | 是否必须 | 说明 |
| --- | --- | --- |
| `model.onnx` | 必须 | ONNX Runtime CPU 推理所需模型 |
| `model_meta.json` | 必须 | 包含模型名、数据集、采样周期、窗口长度、设备列表、输入输出张量名 |
| `normalization.json` | 必须 | 包含 `mains_mean`、`mains_std`、`target_mean`、`target_std` |
| `postprocess.json` | 必须 | 包含事件阈值、最短开关持续时间和可选线性校准参数 |
| `interface_spec.json` | 必须 | 接口版本应为 `nilm_model_interface_v1` |
| `package_manifest.json` | 必须 | 包内文件大小和 SHA-256，用于防止工件漂移 |

如果 GPU 机器上只有训练工件目录，还没有标准 zip，也可以先提供训练工件目录。目录至少需要包含：

```text
model.onnx
model_meta.json
normalization.json
postprocess.json
```

本机可以再使用 `scripts/export_model_package.py` 重新导出标准 zip。

## 4. CSV 字段要求

推理/验收 CSV 至少需要包含：

| 字段 | 是否必须 | 说明 |
| --- | --- | --- |
| `timestamp_utc` | 必须 | UTC 时间戳，供区间筛选和回放排序 |
| `mains_w` | 必须 | 总功率输入 |
| `<appliance>_w` | 必须 | 每个模型输出设备的真值功率列，例如 `kettle_w`、`microwave_w`、`toaster_w` |

CSV 的设备列必须与 `model_meta.json` 中的 `appliances` 一致。若模型输出设备不是 kettle、microwave、toaster，应以模型包元数据为准，并同步调整论文中的基准设备表述。

## 5. 本机 CPU 复现实验步骤

收到模型包和 CSV 后，本机计划执行以下检查：

| 步骤 | 命令或动作 | 预期结果 | 产出 |
| --- | --- | --- | --- |
| 1 | 校验模型包路径和 manifest | 模型包可加载，接口版本匹配 | 校验记录 |
| 2 | 更新 `integration/package_registry.json` active package | 服务可默认加载新包 | 注册表变更 |
| 3 | 运行 `/api/offline/infer` 或服务 API 检查 | 返回离线曲线和指标 | 离线推理结果 |
| 4 | 运行 `run_demo_smoke.py` | `latest.ready=True` 且 `pred_count>0` | smoke 输出 |
| 5 | 整理第 7 章测试证据 | 指标、命令、截图或报告可引用 | 章节证据包 |

## 6. 当前风险

当前仓库已有 Stage-02 源码、服务接口、回放脚本、注册表和论文第五章草稿，但缺少可直接复现的模型包 zip、处理后 CSV 和原始验收报告。没有这些文件时，第 5 章只能说明推理服务设计实现，第 7 章无法形成完整的本机复现实验结论。

## 7. 本机交付状态更新

更新日期：2026-05-12

当前机器已确认为 GPU 训练机。需求表中的 P0/P1 复现实验工件已在本机找到并整理进本次交付分支，后续 CPU 复现实验可直接按 Stage-02 运行手册执行。

| 优先级 | 需求项 | 状态 | 交付路径 |
| --- | --- | --- | --- |
| P0 | 标准模型包 event optimized | 已交付 | `stages/stage-02/model/artifacts/packages/kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip` |
| P0 | 标准模型包 error optimized | 已交付 | `stages/stage-02/model/artifacts/packages/kmt_multi_w301_20260323_155405_calibrated_20260323_161136__error_optimized.zip` |
| P0 | 推理/验收 CSV | 已交付 | `stages/stage-02/model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv` |
| P0 | 模型包对应设备清单 | 已交付 | 模型包内 `model_meta.json`，设备为 `kettle`、`microwave`、`toaster` |
| P1 | 固定区间验收报告 event optimized | 已交付 | `stages/stage-02/model/runs/acceptance_20260323_164509/report.json`、`report.md` |
| P1 | 固定区间验收报告 error optimized | 已交付 | `stages/stage-02/model/runs/acceptance_20260323_164303/report.json`、`report.md` |
| P1 | ONNX parity check | 已交付 | 两个标准模型包内均包含 `onnx_parity_check.json` |
| P1 | 校准/阈值优化报告 | 已交付 | 模型包内包含 `threshold_optimization_report.json` 或相关后处理文件 |

本机已执行以下校验：

```powershell
python integration\manage_package_registry.py verify-active
python integration\run_service_api_checks.py
python integration\run_demo_smoke.py --data-csv model\data\processed\house_1_1s_kmt\timeseries_1s_train_ready.csv --speed 200 --max-rows 320
```

校验结果：

- active package 路径存在。
- API 检查通过，输出 `[api-check] PASS (session + offline + online)`。
- 在线 smoke 通过，输出 `[smoke] PASS`，且 `latest ready=True`、`pred_count=20`。

详细交付记录见：`thesis/chapter_workpacks/第5章_模型包与CPU复现实验本机交付记录_2026-05-12.md`。
