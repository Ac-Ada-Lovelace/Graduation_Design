from __future__ import annotations

from pathlib import Path
import sys
import time

import pandas as pd
from fastapi.testclient import TestClient


STAGE02_ROOT = Path(__file__).resolve().parents[1]
SERVICE_DIR = STAGE02_ROOT / "service"
if str(SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICE_DIR))

from app import app  # noqa: E402


def expect(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    client = TestClient(app)

    r = client.get("/health")
    expect(r.status_code == 200, f"health failed: {r.status_code}")
    health = r.json()
    expect(health.get("status") == "ok", "health.status != ok")
    expect(bool(health.get("registry_active_package")), "health.registry_active_package missing")

    r = client.get("/api/meta")
    expect(r.status_code == 200, f"meta failed: {r.status_code} {r.text}")
    meta = r.json()
    expect(len(meta.get("appliances", [])) > 0, "meta.appliances empty")
    expect(meta.get("data_range", {}).get("start_utc"), "meta.data_range.start_utc missing")
    expect(meta.get("data_range", {}).get("end_utc"), "meta.data_range.end_utc missing")
    expect(isinstance(meta.get("offline_presets"), list), "meta.offline_presets missing")
    expect(isinstance(meta.get("online_presets"), list), "meta.online_presets missing")

    r = client.get("/api/presets/offline")
    expect(r.status_code == 200, f"offline presets failed: {r.status_code}")
    p_off = r.json()
    expect("presets" in p_off, "offline presets payload invalid")

    r = client.get("/api/presets/online")
    expect(r.status_code == 200, f"online presets failed: {r.status_code}")
    p_on = r.json()
    expect("presets" in p_on, "online presets payload invalid")

    start = pd.Timestamp(meta["data_range"]["start_utc"], tz="UTC")
    end = (start + pd.Timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    r = client.post(
        "/api/offline/infer",
        json={
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "end_utc": end,
            "event_tolerance_s": 10,
            "max_points": 4000,
        },
    )
    expect(r.status_code == 200, f"offline infer failed: {r.status_code} {r.text}")
    off = r.json()
    expect(len(off.get("series", {}).get("timestamp_utc", [])) > 10, "offline series too short")
    expect(off.get("metrics", {}).get("mae_avg_w") is not None, "offline mae missing")
    expect(off.get("metrics", {}).get("mean_diff_avg_w") is not None, "offline mean_diff missing")
    expect("diff_w" in off.get("series", {}), "offline diff_w missing")
    expect(off.get("config", {}).get("point_count_full") is not None, "offline point_count_full missing")

    r = client.post(
        "/api/online/start",
        json={
            "start_utc": start.isoformat().replace("+00:00", "Z"),
            "speed": 500,
            "max_rows": 320,
        },
    )
    expect(r.status_code == 200, f"online start failed: {r.status_code} {r.text}")

    done = False
    for _ in range(20):
        time.sleep(0.3)
        r = client.get("/api/online/status")
        expect(r.status_code == 200, f"online status failed: {r.status_code}")
        st = r.json()
        if not st.get("running", False):
            done = True
            break
    expect(done, "online replay did not finish in expected time for check")
    st = client.get("/api/online/status").json()
    expect(int(st.get("sent_rows", 0)) > 0, "online sent_rows == 0")
    expect(int(st.get("latest", {}).get("pred_count", 0)) > 0, "online latest.pred_count == 0")
    expect("event_stream" in st, "online event_stream missing")

    r = client.post("/api/online/stop")
    expect(r.status_code == 200, f"online stop failed: {r.status_code}")

    print("[api-check] PASS (session + offline + online)")


if __name__ == "__main__":
    main()
