import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.seq2point import (  # noqa: E402
    Seq2PointNet,
    build_windows,
    infer_model_variant_from_state_dict,
    load_train_ready_frame,
    split_by_time,
)


def denorm(y_norm: np.ndarray, apps: list[str], norm_json: dict[str, Any]) -> np.ndarray:
    means = np.array([norm_json["target_mean"][a] for a in apps], dtype=np.float32)
    stds = np.array([norm_json["target_std"][a] for a in apps], dtype=np.float32)
    return y_norm * stds + means


def apply_linear_calibration(
    y_pred: np.ndarray,
    apps: list[str],
    rules_json: dict[str, Any],
) -> np.ndarray:
    coeffs = rules_json.get("linear_calibration", {})
    if not isinstance(coeffs, dict) or not coeffs:
        return y_pred
    out = y_pred.copy()
    for i, app in enumerate(apps):
        row = coeffs.get(app, {})
        a = float(row.get("scale_a", 1.0))
        b = float(row.get("bias_b", 0.0))
        out[:, i] = np.clip(a * out[:, i] + b, a_min=0.0, a_max=None)
    return out


def events_from_series(values: np.ndarray, on: float, off: float) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    state = False
    for i, v in enumerate(values):
        if not state and v >= on:
            state = True
            out.append((i, "on"))
        elif state and v <= off:
            state = False
            out.append((i, "off"))
    return out


def match_f1(
    true_events: list[tuple[int, str]],
    pred_events: list[tuple[int, str]],
    typ: str,
    tol_s: int,
) -> float:
    t = [i for i, k in true_events if k == typ]
    p = [i for i, k in pred_events if k == typ]
    if len(t) == 0 and len(p) == 0:
        return 1.0
    if len(t) == 0 or len(p) == 0:
        return 0.0
    used = set()
    matched = 0
    for ti in t:
        best_j = None
        best_d = 10**9
        for j, pj in enumerate(p):
            if j in used:
                continue
            d = abs(pj - ti)
            if d < best_d:
                best_d = d
                best_j = j
        if best_j is not None and best_d <= tol_s:
            used.add(best_j)
            matched += 1
    p_val = matched / max(len(p), 1)
    r_val = matched / max(len(t), 1)
    return 0.0 if (p_val + r_val) == 0 else (2 * p_val * r_val / (p_val + r_val))


def parse_minutes(raw: str) -> list[int]:
    vals = []
    for x in raw.split(","):
        x = x.strip()
        if not x:
            continue
        vals.append(int(x))
    if not vals:
        raise ValueError("minutes cannot be empty")
    return vals


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine high-score showcase segments for a run/artifact.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--artifact-id",
        default="",
        help="Artifact id containing normalization/postprocess. Defaults to --run-id.",
    )
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--minutes", default="10,15,20")
    parser.add_argument("--stride-s", type=int, default=60)
    parser.add_argument("--event-tolerance-s", type=int, default=10)
    parser.add_argument("--min-true-events", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    run_dir = (ROOT / "runs" / args.run_id).resolve()
    artifact_id = args.artifact_id.strip() or args.run_id
    art_dir = (ROOT / "artifacts" / "models" / artifact_id).resolve()
    if not run_dir.exists() or not art_dir.exists():
        raise FileNotFoundError(f"run/artifact not found for run-id={args.run_id}, artifact-id={artifact_id}")

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    apps = summary["appliances"]
    window = int(summary["window_size"])
    norm = json.loads((art_dir / "normalization.json").read_text(encoding="utf-8"))
    rules = json.loads((art_dir / "postprocess.json").read_text(encoding="utf-8-sig"))

    data_csv = Path(args.data_csv)
    frame = load_train_ready_frame(data_csv, apps)
    raw = pd.read_csv(data_csv)
    power_cols = ["mains_w", *[f"{a}_w" for a in apps]]
    if "timestamp_utc" not in raw.columns:
        raise ValueError("data-csv must include timestamp_utc")
    time_cols = ["timestamp_utc"]
    if "epoch_s" in raw.columns:
        time_cols = ["epoch_s", "timestamp_utc"]
    raw = raw[[*time_cols, *power_cols]].dropna(subset=power_cols).reset_index(drop=True)
    if len(raw) != len(frame):
        raise ValueError("Row mismatch after dropna between raw csv and train frame")
    _, _, test_split = split_by_time(
        frame=frame,
        appliances=apps,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    x_test, y_test = build_windows(test_split, window)
    if len(x_test) == 0:
        raise ValueError("No test windows available for mining.")

    x_n = ((x_test - norm["mains_mean"]) / max(norm["mains_std"], 1e-6))[..., np.newaxis].astype(np.float32)
    ckpt = torch.load(run_dir / "best.pt", map_location="cpu")
    variant = str(ckpt.get("model_variant", infer_model_variant_from_state_dict(ckpt["model_state"])))
    model = Seq2PointNet(n_outputs=len(apps), window_size=window, variant=variant)
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    with torch.no_grad():
        y_pred_n = model(torch.from_numpy(x_n)).numpy()
    y_pred = denorm(y_pred_n, apps, norm)
    y_pred = apply_linear_calibration(y_pred, apps, rules)
    y_true = y_test.astype(np.float32)

    n = len(frame)
    val_end = int(n * (args.train_ratio + args.val_ratio))
    center = window // 2
    if "epoch_s" in raw.columns:
        test_epoch = raw["epoch_s"].to_numpy(dtype=np.int64)[val_end:]
        ts_epoch = test_epoch[center : center + len(y_true)]
    else:
        ts_epoch = np.arange(len(y_true), dtype=np.int64)
    test_utc = raw["timestamp_utc"].to_numpy()[val_end:]
    ts_utc = test_utc[center : center + len(y_true)]

    mins_list = parse_minutes(args.minutes)
    stride = max(1, int(args.stride_s))
    top_k = max(1, int(args.top_k))

    all_rows: list[dict[str, Any]] = []
    for mins in mins_list:
        span = mins * 60
        if len(ts_epoch) < span:
            continue
        rows: list[dict[str, Any]] = []
        for st in range(0, len(ts_epoch) - span + 1, stride):
            ed = st + span
            per_scores = []
            true_event_total = 0
            for i, app in enumerate(apps):
                on = float(rules["on_threshold_w"][app])
                off = float(rules["off_threshold_w"][app])
                te = events_from_series(y_true[st:ed, i], on, off)
                pe = events_from_series(y_pred[st:ed, i], on, off)
                true_event_total += len(te)
                f1_on = match_f1(te, pe, "on", tol_s=int(args.event_tolerance_s))
                f1_off = match_f1(te, pe, "off", tol_s=int(args.event_tolerance_s))
                f1_avg = 0.5 * (f1_on + f1_off)
                mae = float(np.mean(np.abs(y_pred[st:ed, i] - y_true[st:ed, i])))
                mae_score = max(0.0, 1.0 - mae / 200.0)
                score = 0.7 * f1_avg + 0.3 * mae_score
                per_scores.append(score)

            if true_event_total < int(args.min_true_events):
                continue

            rows.append(
                {
                    "minutes": mins,
                    "score": float(np.mean(np.array(per_scores, dtype=np.float32))),
                    "true_events_total": int(true_event_total),
                    "start_idx": int(st),
                    "end_idx": int(ed),
                    "start_epoch_s": int(ts_epoch[st]),
                    "end_epoch_s": int(ts_epoch[ed - 1]),
                    "start_timestamp_utc": str(ts_utc[st]),
                    "end_timestamp_utc": str(ts_utc[ed - 1]),
                }
            )
        rows = sorted(rows, key=lambda x: x["score"], reverse=True)[:top_k]
        all_rows.extend(rows)

    all_rows = sorted(all_rows, key=lambda x: (x["minutes"], -x["score"]))
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
        "artifact_id": artifact_id,
        "minutes": mins_list,
        "stride_s": stride,
        "event_tolerance_s": int(args.event_tolerance_s),
        "min_true_events": int(args.min_true_events),
        "top_k": top_k,
        "segments": all_rows,
    }

    out_path = run_dir / f"showcase_segments_{artifact_id}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Showcase segments saved: {out_path}")


if __name__ == "__main__":
    main()
