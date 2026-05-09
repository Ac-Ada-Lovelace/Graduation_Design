# Stage-03 Implementation Plan V1

- Date: 2026-05-07
- Scope: P0 user-facing household power dashboard
- Reference docs:
  - `stage_03_product_page_structure_v_2.md`
  - `stage_03_ui_spec_v_1.md`
  - `STAGE03_FRONTEND_VIEW_CONTRACT.md`

## 1. Implementation Position

Stage-03 is the user-facing application layer. It should consume Stage-02 model
and inference capability, but it should not reuse the Stage-02 demo UI as the
product UI.

P0 should be intentionally small:

1. Dashboard
2. Device Detail
3. System Status
4. Stage-03 BFF view endpoints

## 2. What We Accept From the New Docs

The two newly added GPT-generated docs are useful as design references, but
they should be treated as source material rather than final implementation
authority.

Accepted into P0:

1. Frontend consumes View Data and does not infer state.
2. Dashboard is the normal user entry.
3. Device Detail explains one appliance.
4. System Status is for demo/admin use.
5. Data status must be visible: normal, delayed, disconnected, empty,
   insufficient.
6. Dashboard includes a light today summary even though full History is P1.

## 3. What We Defer

Deferred beyond P0:

1. Full Realtime page.
2. Full History page.
3. Custom date range.
4. Complex advice/anomaly rules.
5. Multi-user login and role permission.
6. Multi-home or multi-site support.
7. Full audit log.
8. Frontend-side calculations from raw samples.

## 4. Proposed Directory Structure

```text
stages/stage-03/
  app/
    backend/
      main.py
      stage02_client.py
      view_models.py
      requirements.txt
    frontend/
      package.json
      index.html
      src/
        App.vue
        main.ts
        router.ts
        api/
          client.ts
        components/
        pages/
          DashboardPage.vue
          DeviceDetailPage.vue
          SystemStatusPage.vue
```

The exact frontend framework can still be chosen at implementation time, but
Vue is a good fit because Stage-02 demo already uses Vue and ECharts.

## 5. Backend Plan

### 5.1 BFF Responsibilities

The Stage-03 backend should:

1. Call Stage-02 APIs.
2. Normalize Stage-02 data into Stage-03 View Data.
3. Provide stable P0 endpoints.
4. Hide Stage-02 response details from the frontend.
5. Provide graceful fallback when Stage-02 is unavailable.

### 5.2 P0 Endpoints

Implement:

1. `GET /api/dashboard`
2. `GET /api/devices/{device_id}`
3. `GET /api/system/status`
4. `POST /api/system/simulation/start`
5. `POST /api/system/simulation/stop`

### 5.3 Current Data Limitations

Stage-02 currently provides strong live/demo status, but it does not yet provide
a persistent day-level store for Stage-03.

P0 handling:

1. Current power and recent events come from Stage-02 online/session status.
2. Today energy can be returned as `null` until an aggregation source exists.
3. Device ranking can use current power for current Top 3.
4. Today device ranking can be empty with `insufficient` status.

This keeps the application honest and avoids fake historical precision.

## 6. Frontend Plan

### 6.1 App Shell

Implement:

1. Sidebar navigation on desktop.
2. Bottom navigation or compact top navigation on mobile.
3. Global service status indicator.
4. Main content area.

### 6.2 P0 Pages

Dashboard:

1. Current estimated total power.
2. Data status and last updated time.
3. Running devices.
4. Current Top 3 devices.
5. Today summary with insufficient-data fallback.
6. Recent events.
7. Advice placeholder.

Device Detail:

1. Device status summary.
2. Today stats with insufficient-data fallback.
3. Device power chart.
4. Recent events.
5. Run segments if backend provides them.

System Status:

1. Stage-02 service status.
2. Model metadata.
3. Data source/simulation status.
4. Start/stop simulation controls.

## 7. Verification Plan

P0 verification should include:

1. Backend smoke: all P0 endpoints return valid JSON.
2. Stage-02 unavailable: frontend displays disconnected state.
3. Empty/insufficient data: Dashboard and Device Detail do not crash.
4. Simulation start/stop: System Status buttons update state.
5. Responsive UI: desktop and mobile layouts remain usable.

## 8. First Coding Step

Recommended first implementation step:

1. Create Stage-03 BFF skeleton.
2. Implement `/api/system/status`.
3. Implement `/api/dashboard` using Stage-02 live status.
4. Add a small smoke script for these endpoints.

Only after the BFF contract works should we build the frontend pages.

