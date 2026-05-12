import argparse
import math
import socket
import struct
import threading
import time
from dataclasses import dataclass


PACKET = struct.Struct("<ii9f")


@dataclass
class WorkerStats:
    device_id: int
    sent: int = 0
    errors: int = 0


def build_packet(device_id: int, sequence: int) -> bytes:
    now = int(time.time())
    phase = time.time() + device_id * 0.37 + sequence * 0.03
    current_a = 4.5 + device_id * 0.18 + math.sin(phase) * 0.6
    current_b = 2.2 + device_id * 0.12 + math.sin(phase * 0.8 + 1.1) * 0.4
    current_c = 1.4 + device_id * 0.08 + math.sin(phase * 1.2 + 2.1) * 0.3
    voltage_a = 220.0 + math.sin(phase * 0.5) * 2.5
    voltage_b = 221.0 + math.sin(phase * 0.55 + 0.4) * 2.0
    voltage_c = 219.5 + math.sin(phase * 0.52 + 0.9) * 2.2
    power_a = current_a * voltage_a * 0.91
    power_b = current_b * voltage_b * 0.88
    power_c = current_c * voltage_c * 0.85
    return PACKET.pack(
        device_id,
        now,
        current_a,
        current_b,
        current_c,
        voltage_a,
        voltage_b,
        voltage_c,
        power_a,
        power_b,
        power_c,
    )


def worker(
    host: str,
    port: int,
    stats: WorkerStats,
    interval: float,
    duration: float,
    start_barrier: threading.Barrier,
) -> None:
    start_barrier.wait()
    end_at = time.monotonic() + duration
    sequence = 0
    try:
        with socket.create_connection((host, port), timeout=5) as conn:
            conn.settimeout(5)
            while time.monotonic() < end_at:
                conn.sendall(build_packet(stats.device_id, sequence))
                stats.sent += 1
                sequence += 1
                if interval > 0:
                    time.sleep(interval)
    except Exception:
        stats.errors += 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--devices", type=int, default=80)
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--interval-ms", type=float, default=100.0)
    args = parser.parse_args()

    interval = max(args.interval_ms, 0.0) / 1000.0
    stats = [WorkerStats(device_id=i) for i in range(1, args.devices + 1)]
    barrier = threading.Barrier(args.devices + 1)
    threads = [
        threading.Thread(
            target=worker,
            args=(args.host, args.port, item, interval, args.duration, barrier),
            daemon=True,
        )
        for item in stats
    ]

    print("Receiver stress sender")
    print(f"target={args.host}:{args.port}")
    print(f"devices={args.devices}")
    print(f"duration_seconds={args.duration}")
    print(f"interval_ms={args.interval_ms}")
    print(f"expected_rate_packets_per_second={args.devices * (1000.0 / args.interval_ms if args.interval_ms > 0 else 0):.2f}")

    started = time.time()
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()
    ended = time.time()

    sent = sum(item.sent for item in stats)
    errors = sum(item.errors for item in stats)
    print(f"actual_duration_seconds={ended - started:.3f}")
    print(f"sent_packets={sent}")
    print(f"connection_errors={errors}")
    print(f"actual_rate_packets_per_second={sent / max(ended - started, 0.001):.2f}")
    print("per_device_min_sent=" + str(min(item.sent for item in stats)))
    print("per_device_max_sent=" + str(max(item.sent for item in stats)))
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
