import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.seq2point import (
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
    ev: list[tuple[int, str]] = []
    state = False
    for i, v in enumerate(values):
        if not state and v >= on:
            state = True
            ev.append((i, "on"))
        elif state and v <= off:
            state = False
            ev.append((i, "off"))
    return ev


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
    match = 0
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
            match += 1
    precision = match / max(len(p), 1)
    recall = match / max(len(t), 1)
    return 0.0 if (precision + recall) == 0 else (2 * precision * recall / (precision + recall))


def eval_event_stats(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    apps: list[str],
    rules: dict[str, Any],
    tol_s: int,
) -> dict[str, Any]:
    per = {}
    vals = []
    for i, a in enumerate(apps):
        on = float(rules["on_threshold_w"][a])
        off = float(rules["off_threshold_w"][a])
        tev = events_from_series(y_true[:, i], on, off)
        pev = events_from_series(y_pred[:, i], on, off)
        f1_on = match_f1(tev, pev, "on", tol_s)
        f1_off = match_f1(tev, pev, "off", tol_s)
        vals.extend([f1_on, f1_off])
        per[a] = {
            "on_threshold_w": on,
            "off_threshold_w": off,
            "f1_on": float(f1_on),
            "f1_off": float(f1_off),
            "f1_avg": float((f1_on + f1_off) / 2.0),
            "true_event_count": len(tev),
            "pred_event_count": len(pev),
        }
    return {
        "f1_avg": float(np.mean(np.array(vals, dtype=np.float32))) if vals else 0.0,
        "per_appliance": per,
    }


def tune_thresholds_for_app(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    old_on: float,
    old_off: float,
    tol_s: int,
) -> tuple[float, float, float]:
    tev_ref = events_from_series(y_true, old_on, old_off)
    if len(tev_ref) == 0:
        return old_on, old_off, 1.0

    pred_pos = y_pred[y_pred > 0]
    if len(pred_pos) < 20:
        return old_on, old_off, 0.0

    q_low = float(np.percentile(pred_pos, 60))
    q_high = float(np.percentile(pred_pos, 99.5))
    if q_high <= q_low:
        q_high = q_low + 1.0

    on_candidates = np.linspace(q_low, q_high, num=25)
    # keep candidates in a sensible physical range around old threshold
    on_candidates = np.clip(on_candidates, 0.1 * old_on, 1.3 * old_on)
    on_candidates = np.unique(on_candidates)

    best = (old_on, old_off, -1.0)
    for on in on_candidates:
        off_candidates = np.linspace(max(1.0, on * 0.2), max(1.0, on * 0.95), num=10)
        for off in off_candidates:
            if off >= on:
                continue
            pev = events_from_series(y_pred, float(on), float(off))
            f1_on = match_f1(tev_ref, pev, "on", tol_s)
            f1_off = match_f1(tev_ref, pev, "off", tol_s)
            score = 0.5 * (f1_on + f1_off)
            # mild penalty if too many predicted events
            score -= 0.02 * max(0, len(pev) - len(tev_ref))
            if score > best[2]:
                best = (float(on), float(off), float(score))
    return best


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize postprocess thresholds and create artifact copy.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--artifact-id",
        default="",
        help="Artifact id to read/write thresholds from. Defaults to --run-id.",
    )
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--tolerance-s", type=int, default=10)
    parser.add_argument(
        "--tune-split",
        choices=["val", "test"],
        default="val",
        help="Which split to use for threshold tuning. 'test' is demo-oriented and leaks evaluation data.",
    )
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
    rules_old = json.loads((art_dir / "postprocess.json").read_text(encoding="utf-8"))

    frame = load_train_ready_frame(Path(args.data_csv), apps)
    _, val_split, test_split = split_by_time(frame, apps, train_ratio=args.train_ratio, val_ratio=args.val_ratio)

    x_val, y_val = build_windows(val_split, window)
    x_test, y_test = build_windows(test_split, window)
    if len(x_val) == 0 or len(x_test) == 0:
        raise ValueError("No val/test windows for threshold optimization")

    x_val_n = ((x_val - norm["mains_mean"]) / max(norm["mains_std"], 1e-6))[..., np.newaxis].astype(np.float32)
    x_test_n = ((x_test - norm["mains_mean"]) / max(norm["mains_std"], 1e-6))[..., np.newaxis].astype(np.float32)

    ckpt = torch.load(run_dir / "best.pt", map_location="cpu")
    variant = str(ckpt.get("model_variant", infer_model_variant_from_state_dict(ckpt["model_state"])))
    model = Seq2PointNet(
        n_outputs=len(apps),
        window_size=window,
        variant=variant,
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()
    with torch.no_grad():
        y_val_pred_n = model(torch.from_numpy(x_val_n)).numpy()
        y_test_pred_n = model(torch.from_numpy(x_test_n)).numpy()

    y_val_pred = denorm(y_val_pred_n, apps, norm)
    y_test_pred = denorm(y_test_pred_n, apps, norm)
    y_val_pred = apply_linear_calibration(y_val_pred, apps, rules_old)
    y_test_pred = apply_linear_calibration(y_test_pred, apps, rules_old)
    y_val_true = y_val.astype(np.float32)
    y_test_true = y_test.astype(np.float32)

    before = eval_event_stats(y_test_true, y_test_pred, apps, rules_old, tol_s=args.tolerance_s)

    if args.tune_split == "test":
        y_tune_true = y_test_true
        y_tune_pred = y_test_pred
    else:
        y_tune_true = y_val_true
        y_tune_pred = y_val_pred

    rules_new = json.loads(json.dumps(rules_old))
    tune_details = {}
    for i, a in enumerate(apps):
        old_on = float(rules_old["on_threshold_w"][a])
        old_off = float(rules_old["off_threshold_w"][a])
        on_new, off_new, score = tune_thresholds_for_app(
            y_true=y_tune_true[:, i],
            y_pred=y_tune_pred[:, i],
            old_on=old_on,
            old_off=old_off,
            tol_s=args.tolerance_s,
        )
        rules_new["on_threshold_w"][a] = float(on_new)
        rules_new["off_threshold_w"][a] = float(off_new)
        tune_details[a] = {
            "old_on": old_on,
            "old_off": old_off,
            "new_on": float(on_new),
            "new_off": float(off_new),
            "val_score": float(score),
        }

    after = eval_event_stats(y_test_true, y_test_pred, apps, rules_new, tol_s=args.tolerance_s)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_run_id = f"{artifact_id}_thopt_{ts}"
    new_art_dir = (ROOT / "artifacts" / "models" / new_run_id).resolve()
    shutil.copytree(art_dir, new_art_dir)
    (new_art_dir / "postprocess.json").write_text(json.dumps(rules_new, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "base_run_id": args.run_id,
        "base_artifact_id": artifact_id,
        "new_run_id": new_run_id,
        "tolerance_s": int(args.tolerance_s),
        "tune_split": args.tune_split,
        "tune_details": tune_details,
        "event_metrics_before": before,
        "event_metrics_after": after,
    }
    (new_art_dir / "threshold_optimization_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Base run: {args.run_id}")
    print(f"New run copy: {new_run_id}")
    print(f"New artifact dir: {new_art_dir}")
    print(f"Event F1 avg before: {before['f1_avg']:.4f}")
    print(f"Event F1 avg after : {after['f1_avg']:.4f}")


if __name__ == "__main__":
    main()
