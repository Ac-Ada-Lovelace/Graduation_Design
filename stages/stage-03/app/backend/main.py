from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from requests import RequestException

from stage02_client import Stage02Client
from view_models import (
    current_devices,
    data_status_from_error,
    display_name,
    latest_pred_map,
    latest_timestamp,
    recent_events,
    series_for_device,
    utc_now,
)


app = FastAPI(title="Stage-03 Household Power Dashboard BFF", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def client() -> Stage02Client:
    return Stage02Client()


def safe_stage02_snapshot() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    c = client()
    try:
        health = c.health()
        meta = c.meta()
        status = c.online_status()
        return health, meta, status, None
    except RequestException as exc:
        return {}, {}, {}, str(exc)
    except Exception as exc:  # noqa: BLE001
        return {}, {}, {}, str(exc)


@app.get("/health")
def health() -> dict[str, Any]:
    _, _, _, err = safe_stage02_snapshot()
    return {
        "status": "ok",
        "stage02_status": data_status_from_error(err),
        "checked_at": utc_now(),
        "error_message": err,
    }


@app.get("/api/system/status")
def system_status() -> dict[str, Any]:
    health_data, meta, status, err = safe_stage02_snapshot()
    stage02_base = client().base_url
    latest_at = latest_timestamp(status)
    model_version = ""
    latest = status.get("latest") if isinstance(status.get("latest"), dict) else {}
    if latest.get("model_version"):
        model_version = str(latest.get("model_version"))
    elif health_data.get("registry_active_package"):
        model_version = str(health_data.get("registry_active_package"))

    return {
        "service": {
            "status": data_status_from_error(err),
            "stage02_base_url": stage02_base,
            "last_heartbeat_at": utc_now() if not err else None,
            "error_message": err,
        },
        "model": {
            "version": model_version or None,
            "interface_version": health_data.get("interface_version"),
            "appliances": meta.get("appliances", []),
            "sample_period_s": meta.get("sample_period_s"),
            "window_size": meta.get("window_size"),
        },
        "data_source": {
            "mode": "simulation",
            "running": bool(status.get("running", False)),
            "speed": status.get("speed"),
            "sent_rows": int(status.get("sent_rows", 0) or 0),
            "latest_data_at": latest_at,
        },
    }


@app.get("/api/dashboard")
def dashboard() -> dict[str, Any]:
    _, meta, status, err = safe_stage02_snapshot()
    appliances = [str(a) for a in meta.get("appliances", [])]
    devices = current_devices(status, appliances) if not err else []
    pred = latest_pred_map(status)
    total_power = sum(max(0.0, v) for v in pred.values()) if pred else None
    top_devices = sorted(devices, key=lambda d: float(d.get("power_w") or 0.0), reverse=True)[:3]
    running = [d for d in devices if d.get("state") == "running"]
    updated_at = latest_timestamp(status)
    data_status = data_status_from_error(err)
    if not err and not updated_at:
        data_status = "insufficient"

    return {
        "data_status": data_status,
        "updated_at": updated_at,
        "total_power_w": total_power,
        "today_energy_kwh": None,
        "running_devices": running,
        "top_devices": top_devices,
        "today_device_ranking": [],
        "recent_events": recent_events(status),
        "advice": {
            "status": "placeholder",
            "title": "暂无明显异常",
            "message": "当前仅展示基础用电状态。",
        },
    }


@app.get("/api/devices/{device_id}")
def device_detail(device_id: str, range: str = "today") -> dict[str, Any]:  # noqa: A002
    _, meta, status, err = safe_stage02_snapshot()
    appliances = [str(a) for a in meta.get("appliances", [])]
    devices = {d["id"]: d for d in current_devices(status, appliances)} if not err else {}
    device = devices.get(
        device_id,
        {
            "id": device_id,
            "name": display_name(device_id),
            "state": "unknown",
            "power_w": None,
            "updated_at": None,
            "data_status": data_status_from_error(err),
        },
    )
    events = [e for e in recent_events(status, limit=30) if e.get("device_id") == device_id]
    series_range = range if range in {"today", "last_hour"} else "today"

    return {
        "device": device,
        "today_stats": {
            "energy_kwh": None,
            "runtime_minutes": None,
            "event_count": len(events),
        },
        "series": {
            "range": series_range,
            "points": series_for_device(status, device_id),
        },
        "run_segments": [],
        "events": events,
    }


@app.post("/api/system/simulation/start")
def simulation_start(payload: dict[str, Any] | None = None) -> dict[str, Any]:
    c = client()
    body = payload or {}
    if not body.get("start_utc"):
        meta = c.meta()
        presets = meta.get("online_presets") if isinstance(meta.get("online_presets"), list) else []
        if presets:
            body["start_utc"] = presets[0].get("start_utc")
            body["end_utc"] = presets[0].get("end_utc")
    body.setdefault("speed", 50)
    body.setdefault("max_rows", 0)
    return c.post_json("/api/online/start", body)


@app.post("/api/system/simulation/stop")
def simulation_stop() -> dict[str, Any]:
    return client().post_json("/api/online/stop", {})

