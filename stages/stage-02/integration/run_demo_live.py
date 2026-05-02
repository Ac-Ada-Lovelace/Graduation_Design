from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any
from urllib import error, parse, request


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
    while time.time() < deadline:
        try:
            health = _get_json(base_url.rstrip("/") + "/health", timeout_s=3.0)
            if health.get("status") == "ok":
                return
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.5)
    raise RuntimeError("Service health check timeout.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage-02 live demo: service + ui (+ optional replay).")
    parser.add_argument("--service-host", default="127.0.0.1")
    parser.add_argument("--service-port", type=int, default=18080)
    parser.add_argument("--ui-port", type=int, default=3000)
    parser.add_argument(
        "--package-zip",
        default="",
        help="Optional package path. If omitted, service uses registry active_package.",
    )
    parser.add_argument("--with-replay", action="store_true")
    parser.add_argument(
        "--data-csv",
        default="model/data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--speed", type=float, default=20.0)
    parser.add_argument("--max-rows", type=int, default=0)
    args = parser.parse_args()

    base_url = f"http://{args.service_host}:{args.service_port}"
    ui_service_param = parse.quote(base_url, safe=":/")
    ui_url = f"http://127.0.0.1:{args.ui_port}/index.html?service={ui_service_param}"

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
    ui_cmd = [
        sys.executable,
        "-m",
        "http.server",
        str(args.ui_port),
    ]

    service_proc: subprocess.Popen[str] | None = None
    ui_proc: subprocess.Popen[str] | None = None
    replay_proc: subprocess.Popen[str] | None = None
    try:
        service_proc = subprocess.Popen(
            service_cmd,
            cwd=str(STAGE02_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _wait_health(base_url, timeout_s=40.0)
        start_payload: dict[str, Any] = {}
        if args.package_zip.strip():
            start_payload["package_zip"] = args.package_zip.strip()
        start_resp = _post_json(base_url + "/session/start", start_payload)

        ui_proc = subprocess.Popen(
            ui_cmd,
            cwd=str((STAGE02_ROOT / "ui").resolve()),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print("[live] Service started")
        print(f"[live] Session model: {start_resp.get('model_name')} window={start_resp.get('window_size')}")
        print(f"[live] UI URL: {ui_url}")
        print("[live] Use UI tabs: 离线展示 / 在线模拟")

        if args.with_replay:
            replay_cmd = [
                sys.executable,
                str((STAGE02_ROOT / "replay" / "stream_csv.py").resolve()),
                "--data-csv",
                str((STAGE02_ROOT / args.data_csv).resolve()),
                "--service-base-url",
                base_url,
                "--speed",
                str(args.speed),
            ]
            if args.max_rows > 0:
                replay_cmd.extend(["--max-rows", str(args.max_rows)])
            print(f"[live] Replay cmd: {' '.join(replay_cmd)}")
            replay_proc = subprocess.Popen(replay_cmd, cwd=str(STAGE02_ROOT))

        print("[live] Press Ctrl+C to stop.")
        while True:
            time.sleep(1.0)
            if service_proc.poll() is not None:
                raise RuntimeError("Service process exited unexpectedly.")
            if ui_proc.poll() is not None:
                raise RuntimeError("UI process exited unexpectedly.")
            if replay_proc is not None and replay_proc.poll() is not None:
                replay_proc = None
    except KeyboardInterrupt:
        print("[live] Stopping...")
    finally:
        for proc in [replay_proc, ui_proc, service_proc]:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()


if __name__ == "__main__":
    main()
