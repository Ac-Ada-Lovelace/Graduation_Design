# Stage 02 SPEC (v0.1)

## 1. 目标

阶段二最终目标：产出可部署的 NILM 推理能力，并通过在线回放完成可展示闭环。

- 训练并导出可推理模型（ONNX 优先）
- 服务可在线接收总线功率并持续输出分电器预测
- 展示层可同时显示 mains / 真值 / 预测 / 事件

## 2. 模块边界

- `model/`：数据处理、训练、导出、模型工件规范
- `service/`：在线推理 API，加载 model 工件
- `replay/`：伪实时数据回放与服务喂数
- `ui/`：演示页面
- `integration/`：联调脚本、彩排流程、验收清单

## 3. 关键约束

- 训练不在当前机器执行；当前机器负责规范与流程定义
- 采样周期参数化，但单个模型工件必须绑定固定 `sample_period_s`
- 所有服务输出必须可追溯到模型工件版本

## 4. 数据与模型契约

### 4.1 输入时序行

字段（最小）：

- `timestamp` (ISO8601 或 epoch_ms)
- `mains_w` (float)
- `kettle_w` (float, 可空)
- `microwave_w` (float, 可空)
- `fridge_w` (float, 可空)

### 4.2 模型输入输出

- 输入张量：`float32 [B, window_size, 1]`
- 输出张量：`float32 [B, N]`，N 为目标电器数

### 4.3 工件包

每个可部署模型包包含：

1. `model.onnx`
2. `model_meta.json`
3. `normalization.json`
4. `postprocess.json`

详细字段见：`model/docs/model_artifact_contract.md`

## 5. 服务 API 规范（MVP）

- `GET /health`
- `POST /session/start`
- `POST /session/reset`
- `POST /session/ingest`
- `GET /session/latest`

`POST /session/ingest` 请求示例：

```json
{
  "timestamp": "2026-03-22T12:00:01Z",
  "mains_w": 612.4
}
```

`GET /session/latest` 响应示例：

```json
{
  "timestamp": "2026-03-22T12:00:01Z",
  "pred_w": {
    "kettle": 0.0,
    "microwave": 0.0,
    "fridge": 121.5
  },
  "events": [
    {"device": "fridge", "type": "on", "confidence": 0.83}
  ],
  "model_version": "seq2point-ukdale-h1-w601-v1"
}
```

## 6. 验收标准

### 6.1 模型侧

- 至少 2-3 个电器模型可导出并可加载
- 导出工件字段完整，版本可追踪

### 6.2 服务侧

- 单用户在线会话稳定运行 >= 10 分钟
- 持续 ingest 不崩溃，latest 可连续返回

### 6.3 演示侧

- 完整跑完 1 段样例
- 同屏展示 mains / 真值 / 预测

## 7. 非目标（本周）

- 不做多用户并发
- 不做多模型融合/复杂调度
- 不追求 SOTA 指标
