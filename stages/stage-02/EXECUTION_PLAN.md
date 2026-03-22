# Stage 02 Execution Plan (Remote-Training Friendly)

## A. 里程碑

1. M1 数据可用性确认（UK-DALE + 目标电器 + 连续片段）
2. M2 模型训练完成（至少 2-3 电器）
3. M3 导出工件并通过本地推理 runner 校验
4. M4 服务接入真实模型工件
5. M5 回放 + UI 闭环演示

## B. 任务拆分

### B1 模型组（优先）

- 选定 house 与目标时间段
- 跑窗口长度对比（301/601/1201）
- 固定最优窗口并训练目标电器
- 导出 ONNX + meta + norm + postprocess

产物：

- `model/artifacts/<run_id>/<appliance>/...`
- 训练报告（损失曲线、样例对比）

### B2 服务组

- 实现 session 生命周期
- ingest -> 维护滑窗 -> 模型推理 -> latest 输出
- 事件生成（阈值 + 迟滞）

产物：

- `service/` API
- 接口文档 + 示例请求

### B3 回放与展示组

- 回放器按固定节拍喂 mains
- 拉取真值与预测并送 UI
- 页面展示对比曲线与当前值

产物：

- `replay/` 运行脚本
- `ui/` 演示页面

### B4 联调与验收

- 一键启动脚本
- 彩排清单与备份方案

产物：

- `integration/` runbook + checklist

## C. 推荐节奏

- Day 1-2: B1
- Day 3: B1/B2
- Day 4: B2/B3
- Day 5: B3/B4
- Day 6-7: 稳定性与汇报材料

## D. 风险闸门

- 若 Day 3 前 3 电器训练不稳：保证 kettle+fridge 先闭环
- 若 1s 标注稀疏：训练侧退到可用周期，服务侧保持 1s 输出节拍
- 若 UI 进度慢：优先可读性，弱化样式复杂度
