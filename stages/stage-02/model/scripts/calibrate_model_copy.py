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

from nilm_stage2.config import load_config
from nilm_stage2.seq2point import (
    Seq2PointNet,
    build_windows,
    infer_model_variant_from_state_dict,
    load_train_ready_frame,
    split_by_time,
)


def denorm(y_norm: np.ndarray, appliances: list[str], norm_json: dict[str, Any]) -> np.ndarray:
    t_mean = np.array([float(norm_json["target_mean"][a]) for a in appliances], dtype=np.float32)
    t_std = np.array([float(norm_json["target_std"][a]) for a in appliances], dtype=np.float32)
    return y_norm * t_std + t_mean


def norm_inputs(x: np.ndarray, norm_json: dict[str, Any]) -> np.ndarray:
    mains_mean = float(norm_json["mains_mean"])
    mains_std = float(norm_json["mains_std"])
    if mains_std < 1e-6:
        mains_std = 1.0
    x_n = (x - mains_mean) / mains_std
    return x_n[..., np.newaxis].astype(np.float32)


def metrics(y_true: np.ndarray, y_pred: np.ndarray, appliances: list[str]) -> dict[str, Any]:
    ae = np.abs(y_pred - y_true)
    se = (y_pred - y_true) ** 2
    mae = ae.mean(axis=0)
    rmse = np.sqrt(se.mean(axis=0))
    return {
        "mae_w": {a: float(mae[i]) for i, a in enumerate(appliances)},
        "rmse_w": {a: float(rmse[i]) for i, a in enumerate(appliances)},
        "mae_w_avg": float(mae.mean()),
        "rmse_w_avg": float(rmse.mean()),
    }


def fit_linear(pred: np.ndarray, truth: np.ndarray) -> tuple[float, float]:
    # Fit truth ~= a * pred + b
    x = pred.astype(np.float64)
    y = truth.astype(np.float64)
    if len(x) < 2 or np.std(x) < 1e-6:
        return 1.0, 0.0

    x_mean = x.mean()
    y_mean = y.mean()
    var_x = np.mean((x - x_mean) ** 2)
    if var_x < 1e-8:
        return 1.0, 0.0

    cov_xy = np.mean((x - x_mean) * (y - y_mean))
    a = cov_xy / var_x
    b = y_mean - a * x_mean

    # Keep coefficients in a safe range for robust deployment.
    # If fitted slope is non-positive, fallback to identity (do not degrade model behavior).
    if a <= 0:
        return 1.0, 0.0

    a = float(np.clip(a, 0.2, 4.0))
    b = float(np.clip(b, -500.0, 500.0))
    return a, b


def estimate_thresholds(
    app: str,
    y_true: np.ndarray,
    y_pred_cal: np.ndarray,
    old_on: float,
    old_off: float,
) -> tuple[float, float]:
    # Use old on-threshold as pseudo-label boundary on true power.
    on_mask = y_true >= old_on
    off_mask = ~on_mask
    if on_mask.sum() < 10 or off_mask.sum() < 10:
        return old_on, old_off

    on_pred = y_pred_cal[on_mask]
    off_pred = y_pred_cal[off_mask]
    on_p10 = float(np.percentile(on_pred, 10))
    off_p95 = float(np.percentile(off_pred, 95))

    candidate_on = (on_p10 + off_p95) / 2.0
    # Keep threshold in a reasonable band around original value.
    low = 0.3 * old_on
    high = 1.5 * old_on
    on_new = float(np.clip(candidate_on, low, high))

    off_candidate = min(off_p95, on_new * 0.8)
    off_new = float(np.clip(off_candidate, 1.0, on_new - 1.0))

    if off_new >= on_new:
        off_new = max(1.0, on_new * 0.7)
    return on_new, off_new


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a calibrated model artifact copy from an existing run (no retraining)."
    )
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--run-id", required=True, help="Existing training run_id, e.g. p3_w601_s42_...")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    args = parser.parse_args()

    run_dir = (ROOT / "runs" / args.run_id).resolve()
    artifact_dir = (ROOT / "artifacts" / "models" / args.run_id).resolve()
    if not run_dir.exists():
        raise FileNotFoundError(f"Run dir not found: {run_dir}")
    if not artifact_dir.exists():
        raise FileNotFoundError(f"Artifact dir not found: {artifact_dir}")

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    appliances = [str(x).strip().lower() for x in summary.get("appliances", [])]
    if not appliances:
        cfg = load_config(args.config)
        appliances = [str(x).strip().lower() for x in cfg.dataset.get("appliances", [])]
    if not appliances:
        raise ValueError("No appliances found in run summary or config dataset.appliances")
    window_size = int(summary["window_size"])

    norm_json = json.loads((artifact_dir / "normalization.json").read_text(encoding="utf-8"))
    rules_old = json.loads((artifact_dir / "postprocess.json").read_text(encoding="utf-8"))

    frame = load_train_ready_frame(args.data_csv, appliances)
    train_split, val_split, test_split = split_by_time(
        frame=frame,
        appliances=appliances,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    _, _ = train_split, None

    x_val, y_val = build_windows(val_split, window_size)
    x_test, y_test = build_windows(test_split, window_size)
    if len(x_val) == 0 or len(x_test) == 0:
        raise ValueError("Not enough val/test windows for calibration")

    x_val_n = norm_inputs(x_val, norm_json)
    x_test_n = norm_inputs(x_test, norm_json)

    ckpt = torch.load(run_dir / "best.pt", map_location="cpu")
    variant = str(ckpt.get("model_variant", infer_model_variant_from_state_dict(ckpt["model_state"])))
    model = Seq2PointNet(
        n_outputs=len(appliances),
        window_size=window_size,
        variant=variant,
    )
    model.load_state_dict(ckpt["model_state"])
    model.eval()

    with torch.no_grad():
        y_val_pred_n = model(torch.from_numpy(x_val_n)).numpy()
        y_test_pred_n = model(torch.from_numpy(x_test_n)).numpy()

    y_val_true = y_val.astype(np.float32)
    y_test_true = y_test.astype(np.float32)
    y_val_pred = denorm(y_val_pred_n, appliances, norm_json)
    y_test_pred = denorm(y_test_pred_n, appliances, norm_json)

    before = metrics(y_test_true, y_test_pred, appliances)

    coeffs: dict[str, dict[str, float]] = {}
    y_val_pred_cal = np.zeros_like(y_val_pred)
    y_test_pred_cal = np.zeros_like(y_test_pred)
    for i, app in enumerate(appliances):
        a, b = fit_linear(y_val_pred[:, i], y_val_true[:, i])
        coeffs[app] = {"scale_a": float(a), "bias_b": float(b)}
        y_val_pred_cal[:, i] = np.clip(a * y_val_pred[:, i] + b, a_min=0.0, a_max=None)
        y_test_pred_cal[:, i] = np.clip(a * y_test_pred[:, i] + b, a_min=0.0, a_max=None)

    after = metrics(y_test_true, y_test_pred_cal, appliances)

    new_rules = dict(rules_old)
    new_rules["linear_calibration"] = coeffs
    on_new: dict[str, float] = {}
    off_new: dict[str, float] = {}
    for i, app in enumerate(appliances):
        old_on = float(rules_old["on_threshold_w"][app])
        old_off = float(rules_old["off_threshold_w"][app])
        on_v, off_v = estimate_thresholds(
            app=app,
            y_true=y_val_true[:, i],
            y_pred_cal=y_val_pred_cal[:, i],
            old_on=old_on,
            old_off=old_off,
        )
        on_new[app] = on_v
        off_new[app] = off_v
    new_rules["on_threshold_w"] = on_new
    new_rules["off_threshold_w"] = off_new

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_run_id = f"{args.run_id}_calibrated_{ts}"
    new_artifact_dir = (ROOT / "artifacts" / "models" / new_run_id).resolve()
    shutil.copytree(artifact_dir, new_artifact_dir)

    (new_artifact_dir / "postprocess.json").write_text(
        json.dumps(new_rules, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (new_artifact_dir / "linear_calibration.json").write_text(
        json.dumps({"linear_calibration": coeffs}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    calibration_report = {
        "base_run_id": args.run_id,
        "calibrated_run_id": new_run_id,
        "window_size": window_size,
        "appliances": appliances,
        "linear_calibration": coeffs,
        "metrics_before": before,
        "metrics_after": after,
        "thresholds_before": {
            "on_threshold_w": rules_old["on_threshold_w"],
            "off_threshold_w": rules_old["off_threshold_w"],
        },
        "thresholds_after": {
            "on_threshold_w": on_new,
            "off_threshold_w": off_new,
        },
    }
    (new_artifact_dir / "calibration_report.json").write_text(
        json.dumps(calibration_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Base run: {args.run_id}")
    print(f"Calibrated copy: {new_run_id}")
    print(f"New artifact dir: {new_artifact_dir}")
    print(f"Before MAE avg (W): {before['mae_w_avg']:.4f}")
    print(f"After  MAE avg (W): {after['mae_w_avg']:.4f}")
    print(f"Before RMSE avg (W): {before['rmse_w_avg']:.4f}")
    print(f"After  RMSE avg (W): {after['rmse_w_avg']:.4f}")


if __name__ == "__main__":
    main()
