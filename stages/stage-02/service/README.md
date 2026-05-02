# Stage-02 / Service

Online inference service for Stage-02 NILM demo.

## Endpoints (MVP)

1. `GET /health`
2. `POST /session/start`
3. `POST /session/reset`
4. `POST /session/ingest`
5. `GET /session/latest`

## Endpoints (Demo V2)

1. `GET /api/meta`
2. `GET /api/presets/offline`
3. `GET /api/presets/online`
2. `POST /api/offline/infer`
3. `POST /api/online/start`
4. `POST /api/online/stop`
5. `GET /api/online/status`

## Install

```bash
cd stages/stage-02/service
pip install -r requirements.txt
```

## Run

From `stages/stage-02`:

```bash
uvicorn service.app:app --host 127.0.0.1 --port 18080
```

## Start session example

```bash
curl -X POST "http://127.0.0.1:18080/session/start" ^
  -H "Content-Type: application/json" ^
  -d "{\"package_zip\":\"artifacts/packages/kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip\"}"
```

Use registry active package (no explicit package path):

```bash
curl -X POST "http://127.0.0.1:18080/session/start" ^
  -H "Content-Type: application/json" ^
  -d "{}"
```

## Offline infer example

```bash
curl -X POST "http://127.0.0.1:18080/api/offline/infer" ^
  -H "Content-Type: application/json" ^
  -d "{\"start_utc\":\"2013-03-24T07:37:52Z\",\"end_utc\":\"2013-03-24T08:00:24Z\",\"event_tolerance_s\":10,\"target_points\":1200}"
```

## Online replay start example

```bash
curl -X POST "http://127.0.0.1:18080/api/online/start" ^
  -H "Content-Type: application/json" ^
  -d "{\"start_utc\":\"2013-03-24T07:27:15Z\",\"speed\":20,\"max_rows\":0}"
```

## Ingest example

```bash
curl -X POST "http://127.0.0.1:18080/session/ingest" ^
  -H "Content-Type: application/json" ^
  -d "{\"timestamp_utc\":\"2013-03-24T07:27:15Z\",\"mains_w\":356.2}"
```
