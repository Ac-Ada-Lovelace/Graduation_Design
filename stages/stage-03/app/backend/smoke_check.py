from __future__ import annotations

from fastapi.testclient import TestClient

from main import app


def expect(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> None:
    client = TestClient(app)

    r = client.get("/health")
    expect(r.status_code == 200, f"health failed: {r.status_code} {r.text}")
    health = r.json()
    expect(health.get("status") == "ok", "health.status must be ok")

    r = client.get("/api/system/status")
    expect(r.status_code == 200, f"system status failed: {r.status_code} {r.text}")
    system = r.json()
    expect("service" in system, "system.service missing")
    expect("model" in system, "system.model missing")
    expect("data_source" in system, "system.data_source missing")

    r = client.get("/api/dashboard")
    expect(r.status_code == 200, f"dashboard failed: {r.status_code} {r.text}")
    dashboard = r.json()
    expect("data_status" in dashboard, "dashboard.data_status missing")
    expect("top_devices" in dashboard, "dashboard.top_devices missing")
    expect("recent_events" in dashboard, "dashboard.recent_events missing")

    device_id = "kettle"
    model = system.get("model", {})
    appliances = model.get("appliances") if isinstance(model.get("appliances"), list) else []
    if appliances:
        device_id = str(appliances[0])
    r = client.get(f"/api/devices/{device_id}")
    expect(r.status_code == 200, f"device failed: {r.status_code} {r.text}")
    device = r.json()
    expect("device" in device, "device.device missing")
    expect("today_stats" in device, "device.today_stats missing")
    expect("series" in device, "device.series missing")
    expect("events" in device, "device.events missing")

    print("[stage03-bff-smoke] PASS")


if __name__ == "__main__":
    main()

