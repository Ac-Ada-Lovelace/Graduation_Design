# Stage-02 / Integration

End-to-end startup and smoke module.

## One-command smoke

From `stages/stage-02`:

```bash
python integration/run_demo_smoke.py ^
  --data-csv model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --speed 20 ^
  --max-rows 500
```

This command starts service, runs replay, checks latest output, then stops service.
By default, service uses `integration/package_registry.json` active package.

## Registry management

List packages and active marker:

```bash
python integration/manage_package_registry.py list
```

Set active package by id:

```bash
python integration/manage_package_registry.py set-active --package-id kmt_error_optimized
```

Verify active package path:

```bash
python integration/manage_package_registry.py verify-active
```

## Live demo launcher

From `stages/stage-02`:

```bash
python integration/run_demo_live.py
```

After launch, open the printed UI URL.
Use UI controls for:

1. 离线区间推理（Offline）
2. 在线模拟回放（Online）

If you still want auto-replay on startup:

```bash
python integration/run_demo_live.py ^
  --with-replay ^
  --data-csv model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --speed 20
```
