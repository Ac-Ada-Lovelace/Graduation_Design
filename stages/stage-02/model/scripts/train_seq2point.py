import argparse
from datetime import datetime
import json
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np
import onnxruntime as ort
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.artifact import ModelMeta, NormalizationStats, PostprocessRules, save_bundle
from nilm_stage2.config import load_config
from nilm_stage2.seq2point import (
    Seq2PointNet,
    build_windows,
    compute_normalization,
    load_train_ready_frame,
    normalize_windows,
    split_by_time,
)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def parse_appliance_list(raw: str) -> list[str]:
    vals = [x.strip().lower() for x in raw.split(",") if x.strip()]
    return vals


def choose_device(device_arg: str) -> torch.device:
    if device_arg == "cuda":
        return torch.device("cuda")
    if device_arg == "cpu":
        return torch.device("cpu")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def maybe_subsample(
    x: np.ndarray, y: np.ndarray, max_samples: int, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    if max_samples <= 0 or len(x) <= max_samples:
        return x, y
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(x), size=max_samples, replace=False)
    idx.sort()
    return x[idx], y[idx]


def denorm_targets(y_norm: np.ndarray, appliances: list[str], norm: NormalizationStats) -> np.ndarray:
    t_mean = np.array([norm.target_mean[a] for a in appliances], dtype=np.float32)
    t_std = np.array([norm.target_std[a] for a in appliances], dtype=np.float32)
    return y_norm * t_std + t_mean


def build_weighted_loss_fn(
    *,
    appliances: list[str],
    norm: NormalizationStats,
    on_threshold_w: dict[str, float],
    on_weight: float,
    loss_type: str,
    huber_delta: float,
    device: torch.device,
):
    if on_weight <= 1.0:
        if loss_type == "huber":
            criterion = nn.SmoothL1Loss(beta=huber_delta)
        else:
            criterion = nn.MSELoss()

        def loss_fn(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
            return criterion(pred, target)

        return loss_fn

    t_mean = torch.tensor([norm.target_mean[a] for a in appliances], dtype=torch.float32, device=device)
    t_std = torch.tensor([norm.target_std[a] for a in appliances], dtype=torch.float32, device=device)
    on_th = torch.tensor([on_threshold_w[a] for a in appliances], dtype=torch.float32, device=device)
    beta = float(huber_delta)

    def loss_fn(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        target_denorm = target * t_std + t_mean
        weight = torch.where(target_denorm >= on_th, torch.tensor(on_weight, device=device), torch.tensor(1.0, device=device))

        err = pred - target
        if loss_type == "huber":
            abs_err = torch.abs(err)
            per_elem = torch.where(abs_err < beta, 0.5 * (err ** 2) / beta, abs_err - 0.5 * beta)
        else:
            per_elem = err ** 2
        return torch.mean(weight * per_elem)

    return loss_fn


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    loss_fn,
    device: torch.device,
) -> float:
    model.train()
    total_loss = 0.0
    total_count = 0
    for xb, yb in loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)
        optimizer.zero_grad(set_to_none=True)
        pred = model(xb)
        loss = loss_fn(pred, yb)
        loss.backward()
        optimizer.step()
        bs = xb.shape[0]
        total_loss += float(loss.item()) * bs
        total_count += bs
    return total_loss / max(total_count, 1)


@torch.no_grad()
def evaluate(model: nn.Module, loader: DataLoader, loss_fn, device: torch.device) -> float:
    model.eval()
    total_loss = 0.0
    total_count = 0
    for xb, yb in loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)
        pred = model(xb)
        loss = loss_fn(pred, yb)
        bs = xb.shape[0]
        total_loss += float(loss.item()) * bs
        total_count += bs
    return total_loss / max(total_count, 1)


@torch.no_grad()
def predict_numpy(model: nn.Module, x: np.ndarray, device: torch.device, batch_size: int) -> np.ndarray:
    model.eval()
    preds: list[np.ndarray] = []
    for i in range(0, len(x), batch_size):
        xb = torch.from_numpy(x[i : i + batch_size]).to(device)
        yb = model(xb).detach().cpu().numpy()
        preds.append(yb)
    if not preds:
        return np.empty((0, 0), dtype=np.float32)
    return np.concatenate(preds, axis=0)


def evaluate_denorm_metrics(
    y_true_norm: np.ndarray, y_pred_norm: np.ndarray, appliances: list[str], norm: NormalizationStats
) -> dict[str, Any]:
    t_mean = {k: float(v) for k, v in norm.target_mean.items()}
    t_std = {k: float(v) for k, v in norm.target_std.items()}

    y_true = y_true_norm.copy()
    y_pred = y_pred_norm.copy()
    for i, app in enumerate(appliances):
        y_true[:, i] = y_true[:, i] * t_std[app] + t_mean[app]
        y_pred[:, i] = y_pred[:, i] * t_std[app] + t_mean[app]

    mae = np.mean(np.abs(y_pred - y_true), axis=0)
    rmse = np.sqrt(np.mean((y_pred - y_true) ** 2, axis=0))

    return {
        "mae_w": {app: float(mae[i]) for i, app in enumerate(appliances)},
        "rmse_w": {app: float(rmse[i]) for i, app in enumerate(appliances)},
        "mae_w_avg": float(np.mean(mae)),
        "rmse_w_avg": float(np.mean(rmse)),
    }


def series_events(values: np.ndarray, on_threshold: float, off_threshold: float) -> list[tuple[int, str]]:
    events: list[tuple[int, str]] = []
    state_on = False
    for i, v in enumerate(values):
        if not state_on and v >= on_threshold:
            state_on = True
            events.append((i, "on"))
        elif state_on and v <= off_threshold:
            state_on = False
            events.append((i, "off"))
    return events


def match_event_lags(
    true_events: list[tuple[int, str]],
    pred_events: list[tuple[int, str]],
    event_type: str,
    tolerance_s: int,
) -> dict[str, Any]:
    t_idx = [i for i, k in true_events if k == event_type]
    p_idx = [i for i, k in pred_events if k == event_type]
    if len(t_idx) == 0 and len(p_idx) == 0:
        return {
            "true_count": 0,
            "pred_count": 0,
            "matched": 0,
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "within_10s_ratio": 1.0,
            "mean_abs_lag_s": 0.0,
            "p90_abs_lag_s": 0.0,
        }
    if len(t_idx) == 0:
        return {
            "true_count": 0,
            "pred_count": len(p_idx),
            "matched": 0,
            "precision": 0.0,
            "recall": 1.0,
            "f1": 0.0,
            "within_10s_ratio": 0.0,
            "mean_abs_lag_s": None,
            "p90_abs_lag_s": None,
        }
    if len(p_idx) == 0:
        return {
            "true_count": len(t_idx),
            "pred_count": 0,
            "matched": 0,
            "precision": 1.0,
            "recall": 0.0,
            "f1": 0.0,
            "within_10s_ratio": 0.0,
            "mean_abs_lag_s": None,
            "p90_abs_lag_s": None,
        }

    used = set()
    lags: list[int] = []
    for ti in t_idx:
        best_j = None
        best_dist = 10**9
        for j, pj in enumerate(p_idx):
            if j in used:
                continue
            d = abs(pj - ti)
            if d < best_dist:
                best_dist = d
                best_j = j
        if best_j is not None and best_dist <= tolerance_s:
            used.add(best_j)
            lags.append(p_idx[best_j] - ti)

    matched = len(lags)
    precision = matched / max(len(p_idx), 1)
    recall = matched / max(len(t_idx), 1)
    f1 = 0.0 if (precision + recall) == 0 else 2 * precision * recall / (precision + recall)

    if matched == 0:
        return {
            "true_count": len(t_idx),
            "pred_count": len(p_idx),
            "matched": 0,
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "within_10s_ratio": 0.0,
            "mean_abs_lag_s": None,
            "p90_abs_lag_s": None,
        }

    arr = np.abs(np.array(lags, dtype=np.float32))
    return {
        "true_count": len(t_idx),
        "pred_count": len(p_idx),
        "matched": matched,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "within_10s_ratio": float(np.mean(arr <= 10)),
        "mean_abs_lag_s": float(np.mean(arr)),
        "p90_abs_lag_s": float(np.percentile(arr, 90)),
    }


def evaluate_event_metrics(
    y_true_denorm: np.ndarray,
    y_pred_denorm: np.ndarray,
    appliances: list[str],
    rules: PostprocessRules,
    tolerance_s: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    f1_vals: list[float] = []
    for i, app in enumerate(appliances):
        on = float(rules.on_threshold_w[app])
        off = float(rules.off_threshold_w[app])
        true_ev = series_events(y_true_denorm[:, i], on_threshold=on, off_threshold=off)
        pred_ev = series_events(y_pred_denorm[:, i], on_threshold=on, off_threshold=off)
        on_stat = match_event_lags(true_ev, pred_ev, event_type="on", tolerance_s=tolerance_s)
        off_stat = match_event_lags(true_ev, pred_ev, event_type="off", tolerance_s=tolerance_s)
        f1_vals.extend([on_stat["f1"], off_stat["f1"]])
        out[app] = {
            "threshold_on_w": on,
            "threshold_off_w": off,
            "on": on_stat,
            "off": off_stat,
        }

    return {
        "per_appliance": out,
        "f1_avg": float(np.mean(np.array(f1_vals, dtype=np.float32))) if f1_vals else 0.0,
    }


def default_thresholds(appliances: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    defaults = {
        "kettle": (1200.0, 100.0),
        "microwave": (700.0, 80.0),
        "toaster": (1200.0, 100.0),
        "fridge": (80.0, 50.0),
    }
    on: dict[str, float] = {}
    off: dict[str, float] = {}
    for app in appliances:
        if app in defaults:
            on[app], off[app] = defaults[app]
        else:
            on[app], off[app] = 100.0, 30.0
    return on, off


def build_balanced_sampler(
    *,
    y_true_denorm: np.ndarray,
    appliances: list[str],
    on_threshold_w: dict[str, float],
    on_sample_weight: float,
) -> tuple[WeightedRandomSampler, dict[str, Any]]:
    if len(y_true_denorm) == 0:
        raise ValueError("Cannot build sampler from empty y_true_denorm")
    if on_sample_weight <= 1.0:
        raise ValueError("on_sample_weight must be > 1.0 for balanced sampler")

    th = np.array([on_threshold_w[a] for a in appliances], dtype=np.float32)
    is_on_any = np.any(y_true_denorm >= th, axis=1)
    weights = np.where(is_on_any, on_sample_weight, 1.0).astype(np.float64)
    sampler = WeightedRandomSampler(
        weights=torch.from_numpy(weights),
        num_samples=len(weights),
        replacement=True,
    )
    stats = {
        "mode": "balanced",
        "on_sample_weight": float(on_sample_weight),
        "on_any_ratio": float(np.mean(is_on_any)),
        "off_any_ratio": float(1.0 - np.mean(is_on_any)),
        "on_any_count": int(np.sum(is_on_any)),
        "off_any_count": int(len(is_on_any) - np.sum(is_on_any)),
    }
    return sampler, stats


def export_onnx(
    model: nn.Module,
    onnx_path: Path,
    window_size: int,
    opset: int,
    device: torch.device,
) -> None:
    model.eval()
    cpu_model = model.to("cpu")
    dummy = torch.randn(1, window_size, 1, dtype=torch.float32)
    torch.onnx.export(
        cpu_model,
        dummy,
        onnx_path,
        input_names=["mains_window"],
        output_names=["pred_power"],
        dynamic_axes={"mains_window": {0: "batch"}, "pred_power": {0: "batch"}},
        opset_version=opset,
    )
    model.to(device)


def onnx_parity_check(
    onnx_path: Path,
    model: nn.Module,
    x_sample: np.ndarray,
    device: torch.device,
) -> dict[str, Any]:
    providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    sess = ort.InferenceSession(str(onnx_path), providers=providers)
    onnx_pred = sess.run(["pred_power"], {"mains_window": x_sample.astype(np.float32)})[0]

    model.eval()
    torch_pred = model(torch.from_numpy(x_sample).to(device)).detach().cpu().numpy()
    max_abs_diff = float(np.max(np.abs(onnx_pred - torch_pred)))
    mean_abs_diff = float(np.mean(np.abs(onnx_pred - torch_pred)))
    return {
        "providers": sess.get_providers(),
        "max_abs_diff": max_abs_diff,
        "mean_abs_diff": mean_abs_diff,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Seq2Point NILM model (multi-output).")
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument("--window-size", type=int, default=None)
    parser.add_argument("--run-name", default=None)
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
        help="Prepared CSV path (read from processed data only)",
    )
    parser.add_argument(
        "--target-appliances",
        default="",
        help="Optional comma-separated appliance subset; default uses dataset.appliances from config.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument(
        "--early-stop-patience",
        type=int,
        default=None,
        help="Stop if val loss does not improve for N epochs (<=0 disables early stop).",
    )
    parser.add_argument(
        "--early-stop-min-delta",
        type=float,
        default=None,
        help="Minimum val-loss improvement to reset early-stop counter.",
    )
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--learning-rate", type=float, default=None)
    parser.add_argument("--model-variant", choices=["avgpool", "classic"], default="classic")
    parser.add_argument("--loss", choices=["mse", "huber"], default="mse")
    parser.add_argument("--huber-delta", type=float, default=1.0)
    parser.add_argument("--on-weight", type=float, default=1.0)
    parser.add_argument("--sampler", choices=["uniform", "balanced"], default="uniform")
    parser.add_argument(
        "--sampler-on-weight",
        type=float,
        default=10.0,
        help="Sample weight multiplier for on-state windows when --sampler=balanced.",
    )
    parser.add_argument("--num-workers", type=int, default=None)
    parser.add_argument("--max-train-samples", type=int, default=0)
    parser.add_argument("--max-val-samples", type=int, default=0)
    parser.add_argument("--max-test-samples", type=int, default=0)
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--skip-export", action="store_true")
    parser.add_argument("--event-match-tolerance-s", type=int, default=10)
    parser.add_argument(
        "--summary-out",
        default="",
        help="Optional extra path to write run summary JSON (in addition to runs/<run_id>/summary.json).",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    project = cfg.raw.get("project", {})
    train_cfg = cfg.raw.get("train", {})
    export_cfg = cfg.raw.get("export", {})
    dataset_cfg = cfg.dataset
    experiment_cfg = cfg.experiment

    seed = int(args.seed if args.seed is not None else project.get("seed", 42))
    set_seed(seed)

    appliances = [str(x).strip().lower() for x in dataset_cfg.get("appliances", [])]
    if args.target_appliances.strip():
        selected = parse_appliance_list(args.target_appliances)
        if not selected:
            raise ValueError("Empty --target-appliances parsed.")
        missing = [a for a in selected if a not in appliances]
        if missing:
            raise ValueError(f"target appliances not in config dataset.appliances: {missing}")
        appliances = selected
    if not appliances:
        raise ValueError("No appliances configured in dataset.appliances")

    window_size = int(
        args.window_size if args.window_size is not None else experiment_cfg.get("default_window_size", 601)
    )
    if window_size % 2 == 0:
        raise ValueError("window-size must be odd")

    run_name = args.run_name or f"w{window_size}_sp{int(dataset_cfg.get('model_sample_period_s', 1))}"
    run_id = f"{run_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    epochs = int(args.epochs if args.epochs is not None else train_cfg.get("epochs", 20))
    early_stop_patience = int(
        args.early_stop_patience
        if args.early_stop_patience is not None
        else train_cfg.get("early_stop_patience", 0)
    )
    early_stop_min_delta = float(
        args.early_stop_min_delta
        if args.early_stop_min_delta is not None
        else train_cfg.get("early_stop_min_delta", 0.0)
    )
    batch_size = int(args.batch_size if args.batch_size is not None else train_cfg.get("batch_size", 64))
    learning_rate = float(
        args.learning_rate if args.learning_rate is not None else train_cfg.get("learning_rate", 1e-4)
    )
    num_workers = int(args.num_workers if args.num_workers is not None else train_cfg.get("num_workers", 0))

    device = choose_device(args.device)
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    frame = load_train_ready_frame(args.data_csv, appliances)
    train_split, val_split, test_split = split_by_time(
        frame=frame,
        appliances=appliances,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
    )
    norm = compute_normalization(train_split, appliances)

    x_train, y_train = build_windows(train_split, window_size)
    x_val, y_val = build_windows(val_split, window_size)
    x_test, y_test = build_windows(test_split, window_size)
    if len(x_train) == 0 or len(x_val) == 0 or len(x_test) == 0:
        raise ValueError("Not enough rows to build windows for train/val/test with current window-size")

    x_train, y_train = maybe_subsample(x_train, y_train, args.max_train_samples, seed)
    x_val, y_val = maybe_subsample(x_val, y_val, args.max_val_samples, seed + 1)
    x_test, y_test = maybe_subsample(x_test, y_test, args.max_test_samples, seed + 2)

    x_train_n, y_train_n = normalize_windows(x_train, y_train, appliances, norm)
    x_val_n, y_val_n = normalize_windows(x_val, y_val, appliances, norm)
    x_test_n, y_test_n = normalize_windows(x_test, y_test, appliances, norm)

    on_th, off_th = default_thresholds(appliances)
    train_ds = TensorDataset(torch.from_numpy(x_train_n), torch.from_numpy(y_train_n))
    sampler_stats: dict[str, Any] = {"mode": "uniform"}
    if args.sampler == "balanced":
        sampler, sampler_stats = build_balanced_sampler(
            y_true_denorm=y_train,
            appliances=appliances,
            on_threshold_w=on_th,
            on_sample_weight=float(args.sampler_on_weight),
        )
        train_loader = DataLoader(
            train_ds,
            batch_size=batch_size,
            sampler=sampler,
            num_workers=num_workers,
            pin_memory=(device.type == "cuda"),
        )
    else:
        train_loader = DataLoader(
            train_ds,
            batch_size=batch_size,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=(device.type == "cuda"),
        )

    val_loader = DataLoader(
        TensorDataset(torch.from_numpy(x_val_n), torch.from_numpy(y_val_n)),
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=(device.type == "cuda"),
    )

    model = Seq2PointNet(
        n_outputs=len(appliances),
        window_size=window_size,
        variant=args.model_variant,
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    norm_stats = NormalizationStats(
        mains_mean=norm.mains_mean,
        mains_std=norm.mains_std,
        target_mean=norm.target_mean,
        target_std=norm.target_std,
    )
    rules = PostprocessRules(
        on_threshold_w=on_th,
        off_threshold_w=off_th,
        min_on_seconds=10,
        min_off_seconds=10,
    )
    loss_fn = build_weighted_loss_fn(
        appliances=appliances,
        norm=norm_stats,
        on_threshold_w=on_th,
        on_weight=float(args.on_weight),
        loss_type=args.loss,
        huber_delta=float(args.huber_delta),
        device=device,
    )

    runs_dir = (ROOT / "runs" / run_id).resolve()
    runs_dir.mkdir(parents=True, exist_ok=True)
    best_ckpt_path = runs_dir / "best.pt"
    metrics_path = runs_dir / "metrics.jsonl"

    best_val = float("inf")
    best_epoch = 0
    no_improve_epochs = 0
    early_stopped = False
    history: list[dict[str, Any]] = []
    for epoch in range(1, epochs + 1):
        train_loss = train_one_epoch(model, train_loader, optimizer, loss_fn, device)
        val_loss = evaluate(model, val_loader, loss_fn, device)
        row = {"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss}
        history.append(row)
        metrics_path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in history) + "\n", encoding="utf-8"
        )
        print(f"[epoch {epoch:03d}] train={train_loss:.6f} val={val_loss:.6f}")

        if val_loss < (best_val - early_stop_min_delta):
            best_val = val_loss
            best_epoch = epoch
            no_improve_epochs = 0
            torch.save(
                {
                    "model_state": model.state_dict(),
                    "epoch": epoch,
                    "val_loss": val_loss,
                    "window_size": window_size,
                    "appliances": appliances,
                    "model_variant": args.model_variant,
                },
                best_ckpt_path,
            )
        else:
            no_improve_epochs += 1

        if early_stop_patience > 0 and no_improve_epochs >= early_stop_patience:
            early_stopped = True
            print(
                f"Early stopping at epoch {epoch}: no val improvement for {no_improve_epochs} epochs "
                f"(patience={early_stop_patience}, min_delta={early_stop_min_delta})."
            )
            break

    ckpt = torch.load(best_ckpt_path, map_location=device)
    model.load_state_dict(ckpt["model_state"])

    y_test_pred_n = predict_numpy(model, x_test_n, device, batch_size=batch_size)
    eval_metrics = evaluate_denorm_metrics(y_test_n, y_test_pred_n, appliances, norm_stats)
    y_test_pred_denorm = denorm_targets(y_test_pred_n, appliances, norm_stats)
    event_metrics = evaluate_event_metrics(
        y_true_denorm=y_test,
        y_pred_denorm=y_test_pred_denorm,
        appliances=appliances,
        rules=rules,
        tolerance_s=int(args.event_match_tolerance_s),
    )

    summary = {
        "run_id": run_id,
        "run_name": run_name,
        "seed": seed,
        "device": str(device),
        "window_size": window_size,
        "appliances": appliances,
        "data_csv": str(Path(args.data_csv).resolve()),
        "split_rows": {
            "train_points": int(len(train_split.mains)),
            "val_points": int(len(val_split.mains)),
            "test_points": int(len(test_split.mains)),
            "train_windows": int(len(x_train_n)),
            "val_windows": int(len(x_val_n)),
            "test_windows": int(len(x_test_n)),
        },
        "epochs_requested": int(epochs),
        "epochs_ran": int(len(history)),
        "best_val_loss": float(best_val),
        "best_epoch": int(best_epoch if best_epoch > 0 else ckpt["epoch"]),
        "model_config": {
            "variant": args.model_variant,
        },
        "loss_config": {
            "loss": args.loss,
            "huber_delta": float(args.huber_delta),
            "on_weight": float(args.on_weight),
        },
        "sampler_config": {
            "sampler": args.sampler,
            "sampler_on_weight": float(args.sampler_on_weight),
            "stats": sampler_stats,
        },
        "early_stop": {
            "enabled": bool(early_stop_patience > 0),
            "patience": int(early_stop_patience),
            "min_delta": float(early_stop_min_delta),
            "triggered": bool(early_stopped),
        },
        "eval_metrics": eval_metrics,
        "event_metrics": event_metrics,
    }
    summary_path = runs_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summary_out:
        extra_summary_path = Path(args.summary_out).resolve()
        extra_summary_path.parent.mkdir(parents=True, exist_ok=True)
        extra_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.skip_export:
        artifacts_root = Path(export_cfg.get("out_dir", "./artifacts/models")).resolve()
        artifact_dir = artifacts_root / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        onnx_path = artifact_dir / "model.onnx"

        opset = int(export_cfg.get("opset", 17))
        export_onnx(model=model, onnx_path=onnx_path, window_size=window_size, opset=opset, device=device)

        meta = ModelMeta(
            model_name=f"seq2point-{run_id}",
            dataset=str(dataset_cfg.get("name", "uk-dale")),
            sample_period_s=float(dataset_cfg.get("model_sample_period_s", 1)),
            window_size=window_size,
            appliances=appliances,
            input_name="mains_window",
            output_name="pred_power",
            input_shape=[1, window_size, 1],
            output_shape=[1, len(appliances)],
        )
        save_bundle(artifact_dir, meta, norm_stats, rules)

        sample_n = min(64, len(x_test_n))
        parity = onnx_parity_check(
            onnx_path=onnx_path,
            model=model,
            x_sample=x_test_n[:sample_n],
            device=device,
        )
        (artifact_dir / "onnx_parity_check.json").write_text(
            json.dumps(parity, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Artifacts exported to: {artifact_dir}")
        print(f"ONNX parity max abs diff: {parity['max_abs_diff']:.8f}")

    print(f"Run summary: {summary_path}")


if __name__ == "__main__":
    main()
