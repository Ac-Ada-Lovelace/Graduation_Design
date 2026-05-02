import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.package_runtime import INTERFACE_VERSION, ModelPackageRuntime


def load_intervals(path: Path) -> list[dict[str, Any]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    intervals = list(raw.get("intervals", []))
    if not intervals:
        raise ValueError(f"No intervals found in: {path}")
    out = []
    for it in intervals:
        out.append(
            {
                "id": str(it["id"]),
                "start_utc": str(it["start_utc"]),
                "end_utc": str(it["end_utc"]),
                "minutes": int(it.get("minutes", 0)),
            }
        )
    return out


def load_eval_frame(csv_path: Path, appliances: list[str]) -> pd.DataFrame:
    needed = ["timestamp_utc", "mains_w", *[f"{a}_w" for a in appliances]]
    df = pd.read_csv(csv_path)
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {csv_path}: {missing}")
    df = df[needed].dropna().reset_index(drop=True)
    if df.empty:
        raise ValueError(f"No valid rows in csv after dropna: {csv_path}")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def predict_frame(
    runtime: ModelPackageRuntime,
    df: pd.DataFrame,
    batch_size: int,
) -> pd.DataFrame:
    mains = df["mains_w"].to_numpy(dtype=np.float32)
    if len(mains) < runtime.window_size:
        raise ValueError(
            f"Not enough rows for window_size={runtime.window_size}: rows={len(mains)}"
        )
    x = np.lib.stride_tricks.sliding_window_view(mains, runtime.window_size).astype(np.float32)
    y_pred = runtime.infer_windows_watts_batched(x, batch_size=batch_size)

    center = runtime.window_size // 2
    rows = len(y_pred)
    ts = df["timestamp_utc"].to_numpy()[center : center + rows]

    out = pd.DataFrame({"timestamp_utc": ts})
    for i, app in enumerate(runtime.appliances):
        out[f"true_{app}_w"] = df[f"{app}_w"].to_numpy(dtype=np.float32)[center : center + rows]
        out[f"pred_{app}_w"] = y_pred[:, i]
    return out


def eval_interval(
    frame_pred: pd.DataFrame,
    runtime: ModelPackageRuntime,
    start_utc: str,
    end_utc: str,
    tolerance_s: int,
) -> dict[str, Any]:
    start = pd.Timestamp(start_utc, tz="UTC")
    end = pd.Timestamp(end_utc, tz="UTC")
    seg = frame_pred[(frame_pred["timestamp_utc"] >= start) & (frame_pred["timestamp_utc"] <= end)].copy()
    if seg.empty:
        raise ValueError(f"Interval has no rows: [{start_utc}, {end_utc}]")

    y_true = np.stack([seg[f"true_{a}_w"].to_numpy(dtype=np.float32) for a in runtime.appliances], axis=1)
    y_pred = np.stack([seg[f"pred_{a}_w"].to_numpy(dtype=np.float32) for a in runtime.appliances], axis=1)

    ae = np.abs(y_pred - y_true)
    se = (y_pred - y_true) ** 2
    mae = ae.mean(axis=0)
    rmse = np.sqrt(se.mean(axis=0))

    per_app = {}
    for i, app in enumerate(runtime.appliances):
        per_app[app] = {"mae_w": float(mae[i]), "rmse_w": float(rmse[i])}

    event = runtime.evaluate_event_f1(y_true, y_pred, tolerance_s=tolerance_s)
    return {
        "rows": int(len(seg)),
        "start_utc": str(seg["timestamp_utc"].iloc[0]),
        "end_utc": str(seg["timestamp_utc"].iloc[-1]),
        "mae_w_avg": float(np.mean(mae)),
        "rmse_w_avg": float(np.mean(rmse)),
        "per_appliance": per_app,
        "event_metrics": event,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Stage-02 fixed-interval acceptance using package zip.")
    parser.add_argument(
        "--package-zip",
        required=True,
        help="Path to exported package zip under artifacts/packages",
    )
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s_kmt/timeseries_1s_train_ready.csv",
    )
    parser.add_argument(
        "--intervals-json",
        default="configs/stage02_acceptance_intervals_kmt.json",
    )
    parser.add_argument("--event-tolerance-s", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4096)
    args = parser.parse_args()

    package_zip = Path(args.package_zip).resolve()
    data_csv = Path(args.data_csv).resolve()
    intervals_json = Path(args.intervals_json).resolve()

    runtime = ModelPackageRuntime.load(package_zip, validate_manifest=True)
    intervals = load_intervals(intervals_json)
    frame = load_eval_frame(data_csv, runtime.appliances)
    pred_frame = predict_frame(runtime, frame, batch_size=args.batch_size)

    rows = []
    for it in intervals:
        r = eval_interval(
            pred_frame,
            runtime,
            start_utc=it["start_utc"],
            end_utc=it["end_utc"],
            tolerance_s=int(args.event_tolerance_s),
        )
        r["id"] = it["id"]
        r["minutes"] = it["minutes"]
        rows.append(r)

    mae_vals = [x["mae_w_avg"] for x in rows]
    rmse_vals = [x["rmse_w_avg"] for x in rows]
    f1_vals = [x["event_metrics"]["f1_avg"] for x in rows]
    aggregate = {
        "mae_w_avg_of_intervals": float(np.mean(np.array(mae_vals, dtype=np.float32))),
        "rmse_w_avg_of_intervals": float(np.mean(np.array(rmse_vals, dtype=np.float32))),
        "event_f1_avg_of_intervals": float(np.mean(np.array(f1_vals, dtype=np.float32))),
    }

    out_dir = (ROOT / "runs" / f"acceptance_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "interface_version": INTERFACE_VERSION,
        "package_zip": str(package_zip),
        "data_csv": str(data_csv),
        "intervals_json": str(intervals_json),
        "appliances": runtime.appliances,
        "window_size": runtime.window_size,
        "sample_period_s": runtime.sample_period_s,
        "onnx_providers": runtime.session.get_providers(),
        "manifest_validated": True,
        "interval_results": rows,
        "aggregate": aggregate,
    }
    report_json = out_dir / "report.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Stage-02 Acceptance Report",
        "",
        f"- Package: `{package_zip.name}`",
        f"- Interface: `{INTERFACE_VERSION}`",
        f"- Appliances: `{runtime.appliances}`",
        "",
        "## Aggregate",
        "",
        f"- MAE avg (interval mean): `{aggregate['mae_w_avg_of_intervals']:.4f} W`",
        f"- RMSE avg (interval mean): `{aggregate['rmse_w_avg_of_intervals']:.4f} W`",
        f"- Event F1 avg (interval mean): `{aggregate['event_f1_avg_of_intervals']:.4f}`",
        "",
        "## Intervals",
        "",
        "| id | minutes | rows | mae_avg_w | rmse_avg_w | event_f1_avg |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        md.append(
            f"| {r['id']} | {r['minutes']} | {r['rows']} | {r['mae_w_avg']:.4f} | "
            f"{r['rmse_w_avg']:.4f} | {r['event_metrics']['f1_avg']:.4f} |"
        )
    (out_dir / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Acceptance report json: {report_json}")
    print(f"Acceptance report md  : {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
