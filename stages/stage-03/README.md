# Stage-03 Application Layer

This stage is the user-facing SaaS application layer of the graduation design.

## Scope

- User/role/permission
- Asset and device management
- Live prediction and event consumption
- Model version traceability in product UI

## Planning Docs

- `APPLICATION_LAYER_PLAN_V1_2026-03-31.md`
- `STAGE03_HOME_APP_MVP_SPEC_V2.md`
- `STAGE03_PAGE_STRUCTURE_DETAIL_V1.md`
- `stage_03_product_page_structure_v_2.md`
- `stage_03_ui_spec_v_1.md`
- `STAGE03_FRONTEND_VIEW_CONTRACT.md`
- `STAGE03_IMPLEMENTATION_PLAN_V1.md`

## Note

Stage-03 consumes outputs from Stage-02 and should not duplicate model training
or protocol parsing internals.

Current mainline product direction:

- User-facing household power dashboard app (MVP), not Stage-02 demo console.

Current implementation baseline:

- P0 focuses on Dashboard, Device Detail, System Status, and a Stage-03 BFF.
- Full Realtime, full History, advice rules, and multi-user permissions are deferred.

P0 app entry:

- Backend: `app/backend/`
- Frontend: `app/frontend/`
