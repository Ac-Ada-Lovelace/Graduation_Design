from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any
from urllib import error, request


def _parse_ts(raw: str) -> datetime:
    txt = raw.strip().replace(" ", "T")
    if txt.endswith("Z"):
        txt = txt[:-1] + "+00:00"
    dt = datetime.fromisoformat(txt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _post_json(url: str, payload: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def _get_json(url: str, timeout_s: float) -> dict[str, Any]:
    req = request.Request(url=url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            data = resp.read().decode("utf-8")
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream prepared CSV rows to Stage-02 ingest endpoint.")
    parser.add_argument(
        "--data-csv",
        default="../model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv",
        help="CSV path containing timestamp_utc,mains_w columns",
    )
    parser.add_argument("--service-base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--speed", type=float, default=10.0, help="Replay speed multiplier (>0).")
    parser.add_argument("--start-ts", default="", help="Optional UTC start timestamp")
    parser.add_argument("--end-ts", default="", help="Optional UTC end timestamp")
    parser.add_argument("--max-rows", type=int, default=0, help="Optional cap for rows replayed")
    parser.add_argument("--timeout-s", type=float, default=10.0)
    parser.add_argument("--log-every", type=int, default=200)
    args = parser.parse_args()

    if args.speed <= 0:
        raise ValueError("--speed must be > 0")

    csv_path = Path(args.data_csv).expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path}")

    start_dt = _parse_ts(args.start_ts) if args.start_ts else None
    end_dt = _parse_ts(args.end_ts) if args.end_ts else None
    ingest_url = args.service_base_url.rstrip("/") + "/session/ingest"
    latest_url = args.service_base_url.rstrip("/") + "/session/latest"

    sent = 0
    skipped = 0
    prev_dt: datetime | None = None
    wall_start = time.time()

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        needed = {"timestamp_utc", "mains_w"}
        if not needed.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"CSV missing columns {needed}, got {reader.fieldnames}")

        for row in reader:
            ts = _parse_ts(str(row["timestamp_utc"]))
            if start_dt and ts < start_dt:
                skipped += 1
                continue
            if end_dt and ts > end_dt:
                break

            mains_w = float(row["mains_w"])
            payload = {
                "timestamp_utc": ts.isoformat().replace("+00:00", "Z"),
                "mains_w": mains_w,
            }
            _post_json(ingest_url, payload, timeout_s=args.timeout_s)
            sent += 1

            if prev_dt is not None:
                delta_s = max((ts - prev_dt).total_seconds(), 0.0)
                sleep_s = delta_s / args.speed
                if sleep_s > 0:
                    time.sleep(sleep_s)
            prev_dt = ts

            if args.log_every > 0 and sent % args.log_every == 0:
                elapsed = max(time.time() - wall_start, 1e-6)
                rate = sent / elapsed
                latest = _get_json(latest_url, timeout_s=args.timeout_s)
                print(
                    f"[replay] sent={sent} skipped={skipped} "
                    f"avg_send_rate={rate:.2f} rows/s latest_ready={latest.get('ready')} "
                    f"latest_ts={latest.get('timestamp_utc')}"
                )

            if args.max_rows > 0 and sent >= args.max_rows:
                break

    elapsed = max(time.time() - wall_start, 1e-6)
    rate = sent / elapsed
    print(f"[replay] completed sent={sent} skipped={skipped} elapsed={elapsed:.2f}s avg_send_rate={rate:.2f} rows/s")


if __name__ == "__main__":
    main()
