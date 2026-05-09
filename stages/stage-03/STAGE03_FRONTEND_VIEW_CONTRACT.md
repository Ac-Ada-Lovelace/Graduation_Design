# Stage-03 Frontend View Contract

- Date: 2026-05-07
- Status: Draft for P0 implementation
- Scope: Dashboard, Device Detail, System Status

## 1. Purpose

This document defines the view data consumed by the Stage-03 frontend.

The frontend should not infer appliance state, pair events, calculate kWh, or
build run segments from raw samples. It should render the view data returned by
the Stage-03 BFF.

## 2. P0 API Surface

P0 frontend only depends on three application-facing endpoints:

1. `GET /api/dashboard`
2. `GET /api/devices/{device_id}`
3. `GET /api/system/status`

The Stage-03 BFF may internally call Stage-02 APIs, but the frontend should not
depend on Stage-02 response shapes.

## 3. Shared Types

### 3.1 DataStatus

Allowed values:

1. `normal`
2. `delayed`
3. `disconnected`
4. `empty`
5. `insufficient`

Display labels:

1. `normal`: 数据正常
2. `delayed`: 数据延迟
3. `disconnected`: 服务断开
4. `empty`: 暂无数据
5. `insufficient`: 数据不足

### 3.2 ApplianceState

Allowed values:

1. `running`
2. `off`
3. `unknown`

Display labels:

1. `running`: 运行中
2. `off`: 关闭
3. `unknown`: 未知

### 3.3 EventType

Allowed values:

1. `on`
2. `off`

### 3.4 DeviceSummary

```json
{
  "id": "kettle",
  "name": "电热水壶",
  "state": "running",
  "power_w": 820.0,
  "power_share": 0.62,
  "updated_at": "2026-05-07T13:42:18Z",
  "data_status": "normal"
}
```

Rules:

1. `power_w` is estimated watts.
2. `power_share` is optional and only meaningful in ranking contexts.
3. Frontend displays `-- W` if `power_w` is null.

### 3.5 EventItem

```json
{
  "id": "evt_001",
  "device_id": "microwave",
  "device_name": "微波炉",
  "type": "on",
  "timestamp": "2026-05-07T13:38:12Z",
  "source": "model"
}
```

Rules:

1. P0 may hide `source`, but the field should exist for future traceability.
2. Clicking an event opens Device Detail for `device_id`.

### 3.6 PowerPoint

```json
{
  "timestamp": "2026-05-07T13:42:18Z",
  "power_w": 820.0
}
```

Rules:

1. Points should already be downsampled or windowed by the BFF.
2. The frontend only renders the sequence.

## 4. Dashboard View

Endpoint:

`GET /api/dashboard`

Response:

```json
{
  "data_status": "normal",
  "updated_at": "2026-05-07T13:42:18Z",
  "total_power_w": 1320.0,
  "today_energy_kwh": 3.42,
  "running_devices": [],
  "top_devices": [],
  "today_device_ranking": [],
  "recent_events": [],
  "advice": {
    "status": "placeholder",
    "title": "暂无明显异常",
    "message": "当前仅展示基础用电状态。"
  }
}
```

Field details:

1. `running_devices`: list of `DeviceSummary`.
2. `top_devices`: list of `DeviceSummary`, sorted by current estimated power.
3. `today_device_ranking`: list of `{ device_id, device_name, energy_kwh, share }`.
4. `recent_events`: list of `EventItem`, newest first.
5. `advice`: P0 placeholder only, not a hard acceptance feature.

P0 fallback:

If today aggregation is unavailable, return:

```json
{
  "today_energy_kwh": null,
  "today_device_ranking": [],
  "data_status": "insufficient"
}
```

The frontend should show a data-insufficient state for the today summary only.

## 5. Device Detail View

Endpoint:

`GET /api/devices/{device_id}?range=today`

Supported P0 ranges:

1. `today`
2. `last_hour`

Response:

```json
{
  "device": {
    "id": "microwave",
    "name": "微波炉",
    "state": "running",
    "power_w": 820.0,
    "updated_at": "2026-05-07T13:42:18Z",
    "data_status": "normal"
  },
  "today_stats": {
    "energy_kwh": 0.84,
    "runtime_minutes": 28,
    "event_count": 6
  },
  "series": {
    "range": "today",
    "points": []
  },
  "run_segments": [],
  "events": []
}
```

Field details:

1. `series.points`: list of `PowerPoint`.
2. `run_segments`: list of `RunSegment`.
3. `events`: list of `EventItem`, newest first.

RunSegment:

```json
{
  "id": "seg_001",
  "start_at": "2026-05-07T10:38:00Z",
  "end_at": "2026-05-07T10:41:00Z",
  "duration_seconds": 180,
  "energy_kwh": 0.04
}
```

P0 fallback:

If run segments are unavailable, return an empty list and keep the event list.
The frontend should not derive segments from events.

## 6. System Status View

Endpoint:

`GET /api/system/status`

Response:

```json
{
  "service": {
    "status": "normal",
    "stage02_base_url": "http://127.0.0.1:18080",
    "last_heartbeat_at": "2026-05-07T13:42:18Z",
    "error_message": null
  },
  "model": {
    "version": "kmt_multi_w301_20260323_155405_thopt_20260323_161139__event_optimized.zip",
    "interface_version": "nilm_model_interface_v1",
    "appliances": ["kettle", "microwave", "toaster"],
    "sample_period_s": 1.0,
    "window_size": 301
  },
  "data_source": {
    "mode": "simulation",
    "running": false,
    "speed": 20.0,
    "sent_rows": 0,
    "latest_data_at": null
  }
}
```

P0 operations:

1. `POST /api/system/simulation/start`
2. `POST /api/system/simulation/stop`

These operations are for demo/admin use and should not appear in the normal
Dashboard flow.

## 7. Non-goals for P0

1. Full Realtime page.
2. Full History page.
3. Custom date range.
4. Multi-user permissions.
5. Strong anomaly detection or advice logic.
6. Frontend-side event pairing or energy aggregation.

