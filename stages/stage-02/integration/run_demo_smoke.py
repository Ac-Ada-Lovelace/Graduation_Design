from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib import error, request


STAGE02_ROOT = Path(__file__).resolve().parents[1]


def _post_json(url: str, payload: dict[str, Any], timeout_s: float = 15.0) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url=url,
        method="POST",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {detail}") from exc


def _get_json(url: str, timeout_s: float = 15.0) -> dict[str, Any]:
    req = request.Request(url=url, method="GET")
    with request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _wait_health(base_url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_err = ""
    while time.time() < deadline:
        try:
            health = _get_json(base_url.rstrip("/") + "/health", timeout_s=3.0)
            if health.get("status") == "ok":
                return
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        time.sleep(0.5)
    raise RuntimeError(f"Service health check timeout. Last error: {last_err}")


def main() -> None:
    parser = argparse.ArgumentParser(description="One-command smoke for Stage-02 demo chain.")
    parser.add_argument("--service-host", default="127.0.0.1")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument(
        "--package-zip",
        default="",
        help="Optional package path. If omitted, service uses registry active_package.",
    )
    parser.add_argument(
        "--data-csv",
        default="model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--speed", type=float, default=20.0)
    parser.add_argument("--max-rows", type=int, default=500)
    parser.add_argument("--log-every", type=int, default=100)
    args = parser.parse_args()

    base_url = f"http://{args.service_host}:{args.service_port}"
    service_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "service.app:app",
        "--host",
        args.service_host,
        "--port",
        str(args.service_port),
        "--log-level",
        "warning",
        "--no-access-log",
    ]

    replay_script = STAGE02_ROOT / "replay" / "stream_csv.py"
    replay_cmd = [
        sys.executable,
        str(replay_script),
        "--data-csv",
        str((STAGE02_ROOT / args.data_csv).resolve()),
        "--service-base-url",
        base_url,
        "--speed",
        str(args.speed),
        "--max-rows",
        str(args.max_rows),
        "--log-every",
        str(args.log_every),
    ]

    service_proc: subprocess.Popen[str] | None = None
    try:
        print(f"[smoke] starting service: {' '.join(service_cmd)}")
        service_proc = subprocess.Popen(
            service_cmd,
            cwd=str(STAGE02_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_health(base_url, timeout_s=40.0)
        print("[smoke] service is healthy")

        start_payload: dict[str, Any] = {}
        if args.package_zip.strip():
            start_payload["package_zip"] = args.package_zip.strip()
        start_resp = _post_json(
            base_url + "/session/start",
            start_payload,
        )
        print(f"[smoke] session started: model={start_resp.get('model_name')} window={start_resp.get('window_size')}")

        print(f"[smoke] replay: {' '.join(replay_cmd)}")
        replay_ret = subprocess.run(replay_cmd, cwd=str(STAGE02_ROOT), check=False)
        if replay_ret.returncode != 0:
            raise RuntimeError(f"Replay failed with code {replay_ret.returncode}")

        latest = _get_json(base_url + "/session/latest")
        print(f"[smoke] latest ready={latest.get('ready')} pred_count={latest.get('pred_count')}")
        print(json.dumps(latest, ensure_ascii=False, indent=2))
        if not latest.get("ready"):
            raise RuntimeError("Latest state is not ready after replay.")
        if int(latest.get("pred_count", 0)) <= 0:
            raise RuntimeError("No predictions were produced.")

        print("[smoke] PASS")
    finally:
        if service_proc is not None:
            service_proc.terminate()
            try:
                service_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                service_proc.kill()


if __name__ == "__main__":
    main()
