# Model Remote Training Runbook

## 1. 目的

本文件用于在远程训练机执行阶段二模型任务，并将工件回传到本仓库。

## 2. 训练机准备

1. 拉取仓库
2. 进入 `stages/stage-02/model`
3. 创建虚拟环境并安装依赖

示例：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## 3. 数据准备（训练机）

- 将 UK-DALE 放入：`model/data/raw/uk-dale`
- 在 `configs/default.json` 中确认：
  - `house`
  - `appliances`
  - `model_sample_period_s`

## 4. 试验与训练

1. 生成窗口对比计划：

```bash
python scripts/window_sweep.py --config configs/default.json
```

2. 按计划逐个窗口训练（待 `train_seq2point.py` 实现）：

```bash
python scripts/train_seq2point.py --config configs/default.json --window-size 601 --run-name w601_sp1
```

3. 固定最优窗口后，训练目标电器并保存 checkpoint。

## 5. 导出工件

导出脚本（待实现）应产出：

- `model.onnx`
- `model_meta.json`
- `normalization.json`
- `postprocess.json`

建议目录：

- `model/artifacts/<run_id>/<appliance>/...`

## 6. 回传与校验

1. 将工件目录同步回本仓库
2. 用 `integration` 校验脚本检查字段完整性
3. 提交工件索引与运行记录，不提交原始大数据
