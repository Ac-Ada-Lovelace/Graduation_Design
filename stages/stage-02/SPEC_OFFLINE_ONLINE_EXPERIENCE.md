# Stage-02 Experience Spec (Offline + Online)

## 1. Goal

Provide a demo-first NILM experience with two user-facing modes:

1. 离线展示：指定区间后批量推理并对比真值/预测/事件。
2. 在线模拟：指定起点后按速度回放数据并实时展示推理效果。

## 2. User Flows

### 2.1 Offline Flow

1. User opens UI and chooses a time interval (manual or preset).
2. User clicks `启动推理`.
3. Backend runs interval inference and returns:
   - true vs pred series
   - numeric metrics
   - event comparison
4. UI renders curve comparison and event timeline comparison.

### 2.2 Online Flow

1. User chooses a start point and replay speed.
2. User clicks `启动在线回放`.
3. Backend runs replay worker that feeds data into session inference.
4. UI polls online status and updates charts in near real time.
5. User can click `停止回放`.

## 3. Backend Contract

Core runtime endpoints:

1. `POST /session/start`
2. `POST /session/reset`
3. `POST /session/ingest`
4. `GET /session/latest`

Experience endpoints:

1. `GET /api/meta`
2. `POST /api/offline/infer`
3. `POST /api/online/start`
4. `POST /api/online/stop`
5. `GET /api/online/status`

## 4. Offline Result Contract

Response includes:

1. `config`: interval and runtime config snapshot
2. `metrics`:
   - `mae_avg_w`
   - `rmse_avg_w`
   - `metrics.event.f1_avg`
   - per-appliance metrics
3. `series`:
   - `timestamp_utc[]`
   - `mains_w[]`
   - `true_w[appliance][]`
   - `pred_w[appliance][]`
4. `events`:
   - `events[appliance].true[]`
   - `events[appliance].pred[]`
   - counts

## 5. Online Status Contract

`GET /api/online/status` returns:

1. worker state: `running`, `sent_rows`, `speed`, `last_error`
2. session snapshot: `latest`
3. rolling history:
   - `history.timestamp_utc[]`
   - `history.true_w[appliance][]`
   - `history.pred_w[appliance][]`
4. rolling metrics:
   - `metrics.mae_avg_w`
   - `metrics.rmse_avg_w`
   - per-appliance metrics

## 6. Frontend Requirements

1. Two tabs: `离线展示` and `在线模拟`.
2. Offline tab must provide:
   - interval selection
   - appliance selector
   - true vs pred line chart
   - event comparison chart
3. Online tab must provide:
   - start/end/speed/max_rows controls
   - start/stop actions
   - live true vs pred chart
   - live event list and rolling metrics

## 7. Data and Model Constraints

1. Mainline baseline:
   - house_1
   - 1-second cadence
   - appliances: kettle/microwave/toaster
2. Raw data remains read-only.
3. Model package loading follows `nilm_model_interface_v1`.

## 8. Non-Functional Requirements

1. CORS enabled for localhost multi-port demo.
2. Fail-fast on invalid timestamps/intervals.
3. Interval payload size limited by `max_points` guard.
4. Online replay is interruptible by stop endpoint.
