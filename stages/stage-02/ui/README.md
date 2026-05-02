# Stage-02 / UI

Vue + ECharts frontend console for Stage-02 demo with two modes:

1. 离线展示：区间推理、真值/预测对比、事件误差与 diff
2. 在线模拟：起点回放、速率控制、实时真值/预测/事件流

Note:

1. Runtime scripts are vendored locally in `ui/vendor/`.
2. No internet access is required for Vue/ECharts loading.

## Run

From `stages/stage-02/ui`:

```bash
python -m http.server 3000
```

Open:

1. `http://127.0.0.1:3000/index.html`
2. If service is not default, pass query param:
   `http://127.0.0.1:3000/index.html?service=http://127.0.0.1:18080`
