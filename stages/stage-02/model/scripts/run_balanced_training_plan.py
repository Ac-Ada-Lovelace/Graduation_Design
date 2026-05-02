import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.config import load_config


def rank_key(row: dict[str, Any]) -> tuple[float, float, float]:
    return (
        float(row["best_val_loss"]),
        float(row["rmse_avg_w"]),
        float(row["mae_avg_w"]),
    )


def parse_seed_list(text: str) -> list[int]:
    vals = []
    for s in text.split(","):
        s = s.strip()
        if not s:
            continue
        vals.append(int(s))
    if not vals:
        raise ValueError("No valid seeds parsed from --final-seeds")
    return vals


def run_train(
    *,
    stage: str,
    run_prefix: str,
    config: str,
    data_csv: str,
    window_size: int,
    seed: int,
    epochs: int,
    patience: int,
    min_delta: float,
    device: str,
    num_workers: int,
    out_dir: Path,
) -> dict[str, Any]:
    summary_out = out_dir / f"{run_prefix}_summary.json"
    run_name = run_prefix
    cmd = [
        sys.executable,
        "scripts/train_seq2point.py",
        "--config",
        config,
        "--data-csv",
        data_csv,
        "--window-size",
        str(window_size),
        "--run-name",
        run_name,
        "--epochs",
        str(epochs),
        "--early-stop-patience",
        str(patience),
        "--early-stop-min-delta",
        str(min_delta),
        "--seed",
        str(seed),
        "--device",
        device,
        "--num-workers",
        str(num_workers),
        "--summary-out",
        str(summary_out),
    ]

    print(f"\n[{stage}] running: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    print(proc.stdout)
    if proc.returncode != 0:
        print(proc.stderr)
        raise RuntimeError(f"Training command failed ({run_prefix}) with exit code {proc.returncode}")

    if not summary_out.exists():
        raise FileNotFoundError(f"Expected summary file not found: {summary_out}")

    summary = json.loads(summary_out.read_text(encoding="utf-8"))
    run_id = summary["run_id"]
    artifact_dir = (ROOT / "artifacts" / "models" / run_id).resolve()

    required_files = [
        artifact_dir / "model.onnx",
        artifact_dir / "model_meta.json",
        artifact_dir / "normalization.json",
        artifact_dir / "postprocess.json",
        artifact_dir / "onnx_parity_check.json",
    ]
    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing artifact files for {run_id}: {missing}")

    parity = json.loads((artifact_dir / "onnx_parity_check.json").read_text(encoding="utf-8"))
    eval_metrics = summary["eval_metrics"]
    result = {
        "stage": stage,
        "run_prefix": run_prefix,
        "run_id": run_id,
        "window_size": int(summary["window_size"]),
        "seed": int(summary["seed"]),
        "epochs_requested": int(summary["epochs_requested"]),
        "epochs_ran": int(summary["epochs_ran"]),
        "best_epoch": int(summary["best_epoch"]),
        "best_val_loss": float(summary["best_val_loss"]),
        "mae_avg_w": float(eval_metrics["mae_w_avg"]),
        "rmse_avg_w": float(eval_metrics["rmse_w_avg"]),
        "summary_path": str(summary_out.resolve()),
        "artifact_dir": str(artifact_dir),
        "onnx_max_abs_diff": float(parity["max_abs_diff"]),
        "onnx_mean_abs_diff": float(parity["mean_abs_diff"]),
    }
    print(
        f"[{stage}] done {run_id} | val={result['best_val_loss']:.6f} "
        f"rmse_avg={result['rmse_avg_w']:.3f} mae_avg={result['mae_avg_w']:.3f}"
    )
    return result


def write_markdown_report(
    report: dict[str, Any], phase1: list[dict[str, Any]], phase2: list[dict[str, Any]], phase3: list[dict[str, Any]], md_path: Path
) -> None:
    def fmt(rows: list[dict[str, Any]]) -> str:
        lines = ["| run_id | window | seed | best_val_loss | rmse_avg_w | mae_avg_w |",
                 "|---|---:|---:|---:|---:|---:|"]
        for r in rows:
            lines.append(
                f"| {r['run_id']} | {r['window_size']} | {r['seed']} | "
                f"{r['best_val_loss']:.6f} | {r['rmse_avg_w']:.3f} | {r['mae_avg_w']:.3f} |"
            )
        return "\n".join(lines)

    text = []
    text.append("# Balanced Training Plan Report")
    text.append("")
    text.append(f"- Created at (UTC): {report['created_at_utc']}")
    text.append(f"- Final window: **{report['final_selection']['window_size']}**")
    text.append(f"- Final run: `{report['final_selection']['run_id']}`")
    text.append(f"- Final artifact: `{report['final_selection']['artifact_dir']}`")
    text.append("")
    text.append("## Phase 1 (10 epoch, patience=2)")
    text.append(fmt(sorted(phase1, key=rank_key)))
    text.append("")
    text.append("## Phase 2 (20 epoch, patience=3)")
    text.append(fmt(sorted(phase2, key=rank_key)))
    text.append("")
    text.append("## Phase 3 (best window, seeds)")
    text.append(fmt(sorted(phase3, key=rank_key)))
    text.append("")
    text.append("## Selection Rule")
    text.append("- Primary: best_val_loss")
    text.append("- Tie-breaker: rmse_avg_w, then mae_avg_w")

    md_path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run balanced 9-training plan for stage-02 model.")
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--base-seed", type=int, default=42)
    parser.add_argument("--final-seeds", default="42,52,62")
    parser.add_argument("--early-stop-min-delta", type=float, default=0.0)
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    cfg = load_config(args.config)
    windows = [int(x) for x in cfg.experiment.get("window_size_candidates", [])]
    if len(windows) < 3:
        raise ValueError("Need at least 3 window_size_candidates for balanced plan")
    windows = windows[:3]
    final_seeds = parse_seed_list(args.final_seeds)
    if len(final_seeds) != 3:
        raise ValueError("Balanced plan expects exactly 3 seeds in --final-seeds")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plan_run_dir = (ROOT / "runs" / f"balanced_plan_{timestamp}").resolve()
    plan_run_dir.mkdir(parents=True, exist_ok=True)

    phase1: list[dict[str, Any]] = []
    for w in windows:
        phase1.append(
            run_train(
                stage="phase1",
                run_prefix=f"p1_w{w}_s{args.base_seed}",
                config=args.config,
                data_csv=args.data_csv,
                window_size=w,
                seed=args.base_seed,
                epochs=10,
                patience=2,
                min_delta=args.early_stop_min_delta,
                device=args.device,
                num_workers=args.num_workers,
                out_dir=plan_run_dir,
            )
        )

    phase2: list[dict[str, Any]] = []
    for w in windows:
        phase2.append(
            run_train(
                stage="phase2",
                run_prefix=f"p2_w{w}_s{args.base_seed}",
                config=args.config,
                data_csv=args.data_csv,
                window_size=w,
                seed=args.base_seed,
                epochs=20,
                patience=3,
                min_delta=args.early_stop_min_delta,
                device=args.device,
                num_workers=args.num_workers,
                out_dir=plan_run_dir,
            )
        )
    phase2_best = sorted(phase2, key=rank_key)[0]
    best_window = int(phase2_best["window_size"])
    print(f"\n[selection] phase2 best window: {best_window}")

    phase3: list[dict[str, Any]] = []
    for seed in final_seeds:
        phase3.append(
            run_train(
                stage="phase3",
                run_prefix=f"p3_w{best_window}_s{seed}",
                config=args.config,
                data_csv=args.data_csv,
                window_size=best_window,
                seed=seed,
                epochs=20,
                patience=3,
                min_delta=args.early_stop_min_delta,
                device=args.device,
                num_workers=args.num_workers,
                out_dir=plan_run_dir,
            )
        )
    final_best = sorted(phase3, key=rank_key)[0]

    report = {
        "plan_name": "balanced_9_runs",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(args.config).resolve()),
        "data_csv": str(Path(args.data_csv).resolve()),
        "windows": windows,
        "base_seed": int(args.base_seed),
        "final_seeds": final_seeds,
        "selection_rule": {
            "primary": "best_val_loss",
            "tie_breaker": ["rmse_avg_w", "mae_avg_w"],
        },
        "phase1": phase1,
        "phase2": phase2,
        "phase3": phase3,
        "phase2_best_window": best_window,
        "final_selection": final_best,
    }

    json_out = Path(args.out).resolve() if args.out else (plan_run_dir / "report.json")
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_out = plan_run_dir / "report.md"
    write_markdown_report(report, phase1, phase2, phase3, md_out)

    print("\nBalanced plan completed.")
    print(f"Report JSON: {json_out}")
    print(f"Report MD: {md_out}")
    print(f"Final selected run: {final_best['run_id']}")
    print(f"Final artifact dir: {final_best['artifact_dir']}")


if __name__ == "__main__":
    main()
