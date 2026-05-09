from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


DEVICE_NAMES = {
    "kettle": "电热水壶",
    "microwave": "微波炉",
    "toaster": "烤面包机",
    "fridge": "冰箱",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def display_name(device_id: str) -> str:
    return DEVICE_NAMES.get(device_id, device_id)


def data_status_from_error(error: str | None) -> str:
    return "disconnected" if error else "normal"


def appliance_state(power_w: float | None, threshold_w: float = 15.0) -> str:
    if power_w is None:
        return "unknown"
    return "running" if float(power_w) >= threshold_w else "off"


def event_id(event: dict[str, Any], idx: int) -> str:
    device = str(event.get("device") or event.get("device_id") or "device")
    typ = str(event.get("type") or "event")
    ts = str(event.get("timestamp_utc") or event.get("timestamp") or idx)
    return f"{device}_{typ}_{ts}_{idx}".replace(":", "").replace("+", "")


def normalize_event(event: dict[str, Any], idx: int) -> dict[str, Any]:
    device_id = str(event.get("device") or event.get("device_id") or "")
    return {
        "id": event_id(event, idx),
        "device_id": device_id,
        "device_name": display_name(device_id),
        "type": str(event.get("type") or "on"),
        "timestamp": event.get("timestamp_utc") or event.get("timestamp"),
        "source": str(event.get("source") or "model"),
    }


def latest_timestamp(status: dict[str, Any]) -> str | None:
    latest = status.get("latest") if isinstance(status.get("latest"), dict) else {}
    ts = latest.get("timestamp_utc")
    if ts:
        return str(ts)
    hist = status.get("history") if isinstance(status.get("history"), dict) else {}
    values = hist.get("timestamp_utc") if isinstance(hist.get("timestamp_utc"), list) else []
    return str(values[-1]) if values else None


def latest_pred_map(status: dict[str, Any]) -> dict[str, float]:
    latest = status.get("latest") if isinstance(status.get("latest"), dict) else {}
    pred = latest.get("pred_w") if isinstance(latest.get("pred_w"), dict) else {}
    return {str(k): float(v) for k, v in pred.items() if v is not None}


def current_devices(status: dict[str, Any], appliances: list[str]) -> list[dict[str, Any]]:
    pred = latest_pred_map(status)
    updated_at = latest_timestamp(status)
    total = sum(max(0.0, float(pred.get(a, 0.0))) for a in appliances)
    rows: list[dict[str, Any]] = []
    for app in appliances:
        power = float(pred.get(app, 0.0)) if app in pred else None
        rows.append(
            {
                "id": app,
                "name": display_name(app),
                "state": appliance_state(power),
                "power_w": power,
                "power_share": (float(power or 0.0) / total) if total > 0 else 0.0,
                "updated_at": updated_at,
                "data_status": "normal" if updated_at else "insufficient",
            }
        )
    return rows


def recent_events(status: dict[str, Any], limit: int = 8) -> list[dict[str, Any]]:
    stream = status.get("event_stream") if isinstance(status.get("event_stream"), dict) else {}
    true_events = stream.get("pred") if isinstance(stream.get("pred"), list) else []
    if not true_events:
        latest = status.get("latest") if isinstance(status.get("latest"), dict) else {}
        true_events = latest.get("events") if isinstance(latest.get("events"), list) else []
    normalized = [normalize_event(e, idx) for idx, e in enumerate(true_events)]
    normalized = [e for e in normalized if e.get("device_id")]
    normalized.sort(key=lambda e: str(e.get("timestamp") or ""), reverse=True)
    return normalized[:limit]


def series_for_device(status: dict[str, Any], device_id: str) -> list[dict[str, Any]]:
    hist = status.get("history") if isinstance(status.get("history"), dict) else {}
    ts = hist.get("timestamp_utc") if isinstance(hist.get("timestamp_utc"), list) else []
    pred_all = hist.get("pred_w") if isinstance(hist.get("pred_w"), dict) else {}
    values = pred_all.get(device_id) if isinstance(pred_all.get(device_id), list) else []
    points = []
    for i, timestamp in enumerate(ts):
        if i >= len(values):
            break
        points.append({"timestamp": timestamp, "power_w": float(values[i])})
    return points

