# Stage-02 / Replay

Pseudo-realtime CSV feeder for the Stage-02 service.

## Run

From `stages/stage-02/replay`:

```bash
python stream_csv.py ^
  --data-csv ../model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv ^
  --service-base-url http://127.0.0.1:18080 ^
  --speed 10
```

## Common options

1. `--start-ts` / `--end-ts`: replay only a selected interval.
2. `--max-rows`: short smoke replay.
3. `--log-every`: progress log interval.
