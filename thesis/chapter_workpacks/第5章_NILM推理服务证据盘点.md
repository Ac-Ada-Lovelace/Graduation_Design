# 第5章 NILM 推理服务模块证据盘点

日期：2026-05-12

## 1. 章节定位

第 5 章建议定位为“NILM 推理服务模块设计实现”。本章承接第 4 章的数据采集与预处理输出，说明结构化量测数据如何进一步进入模型训练、模型包导出、离线区间推理、在线会话推理和回放联调流程。

本章不宜写成“提出一种新的 NILM 算法”。当前仓库证据更适合支撑“将 NILM 模型工程化为可加载、可调用、可切换、可验证的推理服务”。因此，模型训练部分应作为服务链路的前置环节，重点放在数据窗口、模型包契约、接口设计和运行机制。

## 2. 可引用实现文件

### 2.1 模型训练与模型结构

- `stages/stage-02/model/src/nilm_stage2/seq2point.py`
  - `Seq2PointNet`：多输出 Seq2Point 风格卷积网络。
  - `build_windows`：基于滑动窗口构造中心点预测样本。
  - `normalize_windows`、`denormalize_targets`：输入和目标归一化/反归一化。
- `stages/stage-02/model/scripts/train_seq2point.py`
  - 训练、验证、测试划分。
  - 加权采样、事件指标、ONNX 导出和 parity check。
- `stages/stage-02/model/scripts/prepare_house1_timeseries.py`
  - UK-DALE house_1 数据处理入口。

### 2.2 模型包与运行时

- `stages/stage-02/model/docs/model_artifact_contract.md`
  - 模型包必需文件、接口版本、张量输入输出、前后处理规则、热替换约束。
- `stages/stage-02/model/docs/model_system_design.md`
  - 模型侧目录职责、构建流程、验收设计、失败保护。
- `stages/stage-02/model/src/nilm_stage2/package_runtime.py`
  - `ModelPackageRuntime.load`：加载 zip、校验接口版本、校验 manifest 哈希和大小。
  - `infer_windows_watts`、`infer_windows_watts_batched`：模型推理入口。
  - `detect_events`、`evaluate_event_f1`：事件抽取和事件 F1 评价。
- `stages/stage-02/model/scripts/export_model_package.py`
  - 从训练工件导出标准模型包 zip，生成 `interface_spec.json` 和 `package_manifest.json`。

### 2.3 推理服务、回放与集成

- `stages/stage-02/service/app.py`
  - FastAPI 服务。
  - MVP 接口：`/health`、`/session/start`、`/session/reset`、`/session/ingest`、`/session/latest`。
  - Demo V2 接口：`/api/meta`、`/api/offline/infer`、`/api/online/start`、`/api/online/stop`、`/api/online/status`。
  - `SessionRuntime`：在线会话缓冲、滚动窗口推理、事件增量输出。
  - `_offline_infer`：离线区间推理、指标计算、事件对齐。
  - `OnlineReplayController`：在线回放线程、历史真值/预测缓存、在线状态查询。
- `stages/stage-02/replay/stream_csv.py`
  - 按时间戳和倍速向 `/session/ingest` 喂入 CSV 数据。
- `stages/stage-02/integration/run_demo_smoke.py`
  - 启动服务、执行回放、检查 `/session/latest` 是否 ready。
- `stages/stage-02/integration/run_service_api_checks.py`
  - 覆盖 session、offline、online 三类接口的服务检查。
- `stages/stage-02/integration/manage_package_registry.py`
  - 模型包注册、active package 切换和路径校验。

## 3. 可引用项目记录

- `stages/stage-02/README.md`
  - Stage-02 模块划分：model、service、replay、ui、integration。
- `stages/stage-02/PROGRESS_GAP_PLAN_2026-03-23.md`
  - 记录从“仅模型侧较完整”到“服务、回放、UI、集成脚本补齐”的状态变化。
- `stages/stage-02/FINAL_DEMO_RUNBOOK.md`
  - 最终演示命令、active package、离线和在线展示流程、基准指标。
- `stages/stage-02/integration/package_registry.json`
  - 两个 accepted package 的注册信息和聚合指标。
- `stages/stage-02/model/docs/stage02_deploy_acceptance.md`
  - 模型包导出和固定区间验收命令。

## 4. 当前证据缺口

当前工作区包含 Stage-02 源码、设计文档、注册表和运行手册，但未看到实际 `artifacts/packages/` 模型包 zip，也未看到 `model/runs/acceptance_*/report.json` 原始验收报告目录。因此：

1. 第 5 章正文可以引用“注册表和运行手册记录的基准包与指标”，但措辞应写为项目记录中的基准结果，不要写成当前工作区即时复现实验结果。
2. 第 7 章正式测试前，建议补回模型包、验收报告和处理后的 CSV，或重新跑一次 `verify-active`、`run_service_api_checks.py`、`run_demo_smoke.py`。
3. 如果短期无法补齐工件，第 5 章中可保留设计实现描述，把指标表的最终引用放到第 7 章再落定。

## 5. 建议图表

- 图5-1 NILM 推理服务处理流程图：采集记录/公开数据集 -> 窗口构造 -> 模型推理 -> 后处理 -> API 输出。
- 图5-2 模型包结构示意图：`model.onnx`、`model_meta.json`、`normalization.json`、`postprocess.json`、`interface_spec.json`、`package_manifest.json`。
- 表5-1 模型包文件说明。
- 表5-2 推理服务接口说明。
- 表5-3 模型包注册信息。
- 表5-4 在线会话状态字段说明。
