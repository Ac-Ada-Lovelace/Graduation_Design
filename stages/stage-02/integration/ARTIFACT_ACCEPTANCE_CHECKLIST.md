# Artifact Acceptance Checklist

## 必填文件

- [ ] model.onnx
- [ ] model_meta.json
- [ ] normalization.json
- [ ] postprocess.json

## 字段完整性

- [ ] `sample_period_s` 已填写
- [ ] `window_size` 已填写
- [ ] `appliances` 与服务配置一致
- [ ] `input_shape` / `output_shape` 与 ONNX 一致
- [ ] 归一化参数来自训练统计而非临时估计

## 可运行性

- [ ] runner 可成功加载 ONNX
- [ ] 输入一段窗口可输出预测数组
- [ ] 输出数值范围合理（无大面积 NaN/Inf）

## 可追溯性

- [ ] run_id 与 git commit 对应
- [ ] 训练配置已归档
- [ ] 评估摘要已归档
