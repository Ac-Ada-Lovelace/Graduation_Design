import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np
import pandas as pd
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.config import load_config
from nilm_stage2.seq2point import (
    Seq2PointNet,
    build_windows,
    infer_model_variant_from_state_dict,
    load_train_ready_frame,
    split_by_time,
)


def run_train(cmd: list[str], workdir: Path) -> None:
    print(f"\n[run] {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=workdir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line.rstrip())
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"Train command failed with exit code {ret}")


def pick_event_f1(summary: dict[str, Any], appliances: list[str]) -> float:
    em = summary.get("event_metrics", {})
    if "f1_avg" in em:
        return float(em["f1_avg"])
    per = em.get("per_appliance", {})
    vals = []
    for a in appliances:
        aa = per.get(a, {})
        on = aa.get("on", {}).get("f1")
        off = aa.get("off", {}).get("f1")
        if on is not None:
            vals.append(float(on))
        if off is not None:
            vals.append(float(off))
    return float(np.mean(vals)) if vals else 0.0


def rank_runs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    # Event-first ranking for showcase: high event_f1, then low val loss, then low MAE.
    return sorted(rows, key=lambda r: (-r["event_f1_avg"], r["best_val_loss"], r["mae_w_avg"]))


def denorm(y_norm: np.ndarray, apps: list[str], norm_json: dict[str, Any]) -> np.ndarray:
    means = np.array([norm_json["target_mean"][a] for a in apps], dtype=np.float32)
    stds = np.array([norm_json["target_std"][a] for a in apps], dtype=np.float32)
    return y_norm * stds + means


def events_from_series(values: np.ndarray, on: float, off: float) -> list[tuple[int, str]]:
    events: list[tuple[int, str]] = []
    state = False
    for i, v in enumerate(values):
        if not state and v >= on:
            state = True
            events.append((i, "on"))
        elif state and v <= off:
            state = False
            events.append((i, "off"))
    return events


def event_window_score(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    on: float,
    off: float,
    tolerance_s: int,
) -> float:
    true_ev = events_from_series(y_true, on, off)
    pred_ev = events_from_series(y_pred, on, off)

    t_on = [i for i, k in true_ev if k == "on"]
    p_on = [i for i, k in pred_ev if k == "on"]
    if len(t_on) == 0 and len(p_on) == 0:
        f1_on = 1.0
    elif len(t_on) == 0 or len(p_on) == 0:
        f1_on = 0.0
    else:
        used = set()
        match = 0
        for ti in t_on:
            best_j = None
            best_d = 10**9
            for j, pj in enumerate(p_on):
                if j in used:
                    continue
                d = abs(pj - ti)
                if d < best_d:
                    best_d = d
                    best_j = j
            if best_j is not None and best_d <= tolerance_s:
                used.add(best_j)
                match += 1
        p = match / max(len(p_on), 1)
        r = match / max(len(t_on), 1)
        f1_on = 0.0 if (p + r) == 0 else (2 * p * r / (p + r))

    mae = float(np.mean(np.abs(y_pred - y_true)))
    # Convert MAE to a [0,1] score with a soft cap for showcase scoring.
    mae_score = max(0.0, 1.0 - (mae / 200.0))
    return 0.65 * f1_on + 0.35 * mae_score


def mine_showcase_segments(
    *,
    run_id: str,
    data_csv: Path,
    train_ratio: float,
    val_ratio: float,
    win_minutes: list[int],
    stride_s: int,
    tolerance_s: int,
) -> dict[str, Any]:
    run_dir = (ROOT / "runs" / run_id).resolve()
    art_dir = (ROOT / "artifacts" / "models" / run_id).resolve()
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    apps = summary["appliances"]
    window_size = int(summary["window_size"])

    norm = json.loads((art_dir / "normalization.json").read_text(encoding="utf-8"))
    rules = json.loads((art_dir / "postprocess.json").read_text(encoding="utf-8"))

    frame = load_train_ready_frame(data_csv, apps)
    _, _, test_split = split_by_time(frame, apps, train_ratio=train_ratio, val_ratio=val_ratio)
    x_test, y_test = build_windows(test_split, window_size)
    if len(x_test) == 0:
        raise ValueError("No test windows for segment mining")

    x = ((x_test - norm["mains_mean"]) / max(norm["mains_std"], 1e-6))[..., np.newaxis].astype(np.float32)
    ckpt = torch.load(run_dir / "best.pt", map_location="cpu")
    variant = str(ckpt.get("model_variant", infer_model_variant_from_state_dict(ckpt["model_state"])))
    model = Seq2PointNet(
        n_outputs=len(apps),
        window_size=window_size,
        variant=variant,
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    with torch.no_grad():
        y_pred_n = model(torch.from_numpy(x)).numpy()
    y_pred = denorm(y_pred_n, apps, norm)
    y_true = y_test.astype(np.float32)

    center = window_size // 2
    # Build test timestamps aligned with center point.
    n = len(frame)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    test_epoch = frame["epoch_s"].to_numpy(dtype=np.int64)[val_end:]
    test_utc = frame["timestamp_utc"].to_numpy()[val_end:]
    ts_epoch = test_epoch[center : center + len(y_true)]
    ts_utc = test_utc[center : center + len(y_true)]

    segments: list[dict[str, Any]] = []
    for mins in win_minutes:
        span = mins * 60
        if len(ts_epoch) < span:
            continue
        best = None
        for start in range(0, len(ts_epoch) - span + 1, max(1, stride_s)):
            end = start + span
            # Multi-appliance showcase score: mean of per-appliance score.
            per_scores = []
            for i, a in enumerate(apps):
                on = float(rules["on_threshold_w"][a])
                off = float(rules["off_threshold_w"][a])
                s = event_window_score(
                    y_true=y_true[start:end, i],
                    y_pred=y_pred[start:end, i],
                    on=on,
                    off=off,
                    tolerance_s=tolerance_s,
                )
                per_scores.append(s)
            score = float(np.mean(per_scores))
            if (best is None) or (score > best["score"]):
                best = {
                    "minutes": mins,
                    "score": score,
                    "start_idx": int(start),
                    "end_idx": int(end),
                    "start_epoch_s": int(ts_epoch[start]),
                    "end_epoch_s": int(ts_epoch[end - 1]),
                    "start_timestamp_utc": str(ts_utc[start]),
                    "end_timestamp_utc": str(ts_utc[end - 1]),
                }
        if best is not None:
            segments.append(best)

    segments = sorted(segments, key=lambda x: x["score"], reverse=True)
    return {
        "run_id": run_id,
        "segments": segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="3-5h showcase sprint runner (event-priority).")
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--event-tolerance-s", type=int, default=10)
    parser.add_argument("--stride-s", type=int, default=60)
    args = parser.parse_args()

    cfg = load_config(args.config)
    windows = [int(x) for x in cfg.experiment.get("window_size_candidates", [601])]

    data_csv = Path(args.data_csv).resolve()
    out_dir = (ROOT / "runs" / f"sprint_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    experiments = []
    # Multi-output event-priority candidates.
    for w in windows[:3]:
        experiments.append(
            {
                "name": f"multi_classic_bal_w{w}",
                "window": w,
                "target": "",
                "loss": "huber",
                "on_weight": 8.0,
                "sampler": "balanced",
                "sampler_on_weight": 12.0,
                "model_variant": "classic",
                "epochs": 20,
                "patience": 4,
                "seed": 42,
            }
        )

    # Ablation runs to validate sampler impact.
    for w in [301, 601]:
        experiments.append(
            {
                "name": f"multi_classic_uni_w{w}",
                "window": w,
                "target": "",
                "loss": "huber",
                "on_weight": 8.0,
                "sampler": "uniform",
                "sampler_on_weight": 1.0,
                "model_variant": "classic",
                "epochs": 20,
                "patience": 4,
                "seed": 42,
            }
        )

    # Single-appliance specialists for strong event loads.
    for app in ["kettle", "microwave"]:
        experiments.append(
            {
                "name": f"single_{app}_classic_bal_w601",
                "window": 601,
                "target": app,
                "loss": "huber",
                "on_weight": 10.0,
                "sampler": "balanced",
                "sampler_on_weight": 20.0,
                "model_variant": "classic",
                "epochs": 20,
                "patience": 4,
                "seed": 42,
            }
        )

    results: list[dict[str, Any]] = []
    for exp in experiments:
        summary_out = out_dir / f"{exp['name']}_summary.json"
        cmd = [
            sys.executable,
            "scripts/train_seq2point.py",
            "--config",
            args.config,
            "--data-csv",
            str(data_csv),
            "--window-size",
            str(exp["window"]),
            "--run-name",
            exp["name"],
            "--epochs",
            str(exp["epochs"]),
            "--early-stop-patience",
            str(exp["patience"]),
            "--seed",
            str(exp["seed"]),
            "--device",
            args.device,
            "--num-workers",
            str(args.num_workers),
            "--loss",
            exp["loss"],
            "--on-weight",
            str(exp["on_weight"]),
            "--sampler",
            exp["sampler"],
            "--sampler-on-weight",
            str(exp["sampler_on_weight"]),
            "--model-variant",
            exp["model_variant"],
            "--event-match-tolerance-s",
            str(args.event_tolerance_s),
            "--summary-out",
            str(summary_out),
        ]
        if exp["target"]:
            cmd.extend(["--target-appliances", exp["target"]])
        run_train(cmd, ROOT)
        summary = json.loads(summary_out.read_text(encoding="utf-8"))
        apps = summary["appliances"]
        row = {
            "experiment": exp["name"],
            "run_id": summary["run_id"],
            "window_size": int(summary["window_size"]),
            "appliances": apps,
            "best_val_loss": float(summary["best_val_loss"]),
            "mae_w_avg": float(summary["eval_metrics"]["mae_w_avg"]),
            "rmse_w_avg": float(summary["eval_metrics"]["rmse_w_avg"]),
            "event_f1_avg": pick_event_f1(summary, apps),
            "artifact_dir": str((ROOT / "artifacts" / "models" / summary["run_id"]).resolve()),
            "summary_path": str(summary_out.resolve()),
            "loss": exp["loss"],
            "on_weight": float(exp["on_weight"]),
            "sampler": exp["sampler"],
            "sampler_on_weight": float(exp["sampler_on_weight"]),
            "model_variant": exp["model_variant"],
            "target": exp["target"] or "multi",
        }
        results.append(row)

    ranked = rank_runs(results)
    best = ranked[0]
    print(f"\n[best] {best['run_id']} | event_f1={best['event_f1_avg']:.4f} val={best['best_val_loss']:.6f}")

    # Mine showcase segments for the best multi-appliance run if available; otherwise best run.
    multi_ranked = [r for r in ranked if r["target"] == "multi"]
    segment_run_id = multi_ranked[0]["run_id"] if multi_ranked else best["run_id"]
    segment_info = mine_showcase_segments(
        run_id=segment_run_id,
        data_csv=data_csv,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        win_minutes=[10, 15, 20],
        stride_s=args.stride_s,
        tolerance_s=args.event_tolerance_s,
    )

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(args.config).resolve()),
        "data_csv": str(data_csv),
        "results": ranked,
        "best_overall": best,
        "segment_source_run_id": segment_run_id,
        "showcase_segments": segment_info["segments"],
        "selection_rule": {
            "primary": "event_f1_avg desc",
            "secondary": "best_val_loss asc",
            "tertiary": "mae_w_avg asc",
        },
    }

    report_json = out_dir / "sprint_report.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Showcase Sprint Report",
        "",
        f"- Best overall: `{best['run_id']}`",
        f"- Segment source run: `{segment_run_id}`",
        "",
        "## Top 5",
        "",
        "| run_id | target | variant | sampler | window | event_f1_avg | val_loss | mae_avg_w | rmse_avg_w |",
        "|---|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in ranked[:5]:
        md_lines.append(
            f"| {r['run_id']} | {r['target']} | {r['model_variant']} | {r['sampler']} | {r['window_size']} | {r['event_f1_avg']:.4f} | "
            f"{r['best_val_loss']:.6f} | {r['mae_w_avg']:.3f} | {r['rmse_w_avg']:.3f} |"
        )
    md_lines.extend(["", "## Showcase Segments", ""])
    md_lines.append("| minutes | score | start_epoch_s | end_epoch_s |")
    md_lines.append("|---:|---:|---:|---:|")
    for s in segment_info["segments"]:
        md_lines.append(
            f"| {s['minutes']} | {s['score']:.4f} | {s['start_epoch_s']} | {s['end_epoch_s']} |"
        )
    (out_dir / "sprint_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"\nSprint report: {report_json}")
    print(f"Sprint markdown: {out_dir / 'sprint_report.md'}")


if __name__ == "__main__":
    main()
