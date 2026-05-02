import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def run_cmd(cmd: list[str], cwd: Path) -> None:
    print(f"\n[run] {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line.rstrip())
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"Command failed with exit code {ret}")


def pick_event_f1(summary: dict[str, Any], appliances: list[str]) -> float:
    em = summary.get("event_metrics", {})
    if "f1_avg" in em:
        return float(em["f1_avg"])
    per = em.get("per_appliance", {})
    vals: list[float] = []
    for app in appliances:
        row = per.get(app, {})
        on = row.get("on", {}).get("f1")
        off = row.get("off", {}).get("f1")
        if on is not None:
            vals.append(float(on))
        if off is not None:
            vals.append(float(off))
    return float(np.mean(vals)) if vals else 0.0


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            -r["event_f1_avg"],
            r["mae_w_avg"],
            r["rmse_w_avg"],
            r["best_val_loss"],
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine multi-appliance event performance around current best setup.")
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--event-tolerance-s", type=int, default=10)
    args = parser.parse_args()

    out_dir = (ROOT / "runs" / f"event_refine_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_csv = str(Path(args.data_csv).resolve())

    experiments = [
        {
            "name": "ref_multi_w301_u8_s42",
            "window": 301,
            "seed": 42,
            "on_weight": 8.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w301_u8_s52",
            "window": 301,
            "seed": 52,
            "on_weight": 8.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w301_u8_s62",
            "window": 301,
            "seed": 62,
            "on_weight": 8.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w301_u10_s42",
            "window": 301,
            "seed": 42,
            "on_weight": 10.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w301_b10_s42",
            "window": 301,
            "seed": 42,
            "on_weight": 10.0,
            "sampler": "balanced",
            "sampler_on_weight": 12.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w451_u8_s42",
            "window": 451,
            "seed": 42,
            "on_weight": 8.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
        {
            "name": "ref_multi_w451_u10_s42",
            "window": 451,
            "seed": 42,
            "on_weight": 10.0,
            "sampler": "uniform",
            "sampler_on_weight": 1.0,
            "lr": 1e-4,
            "huber_delta": 1.0,
        },
    ]

    rows: list[dict[str, Any]] = []
    for exp in experiments:
        summary_out = out_dir / f"{exp['name']}_summary.json"
        cmd = [
            sys.executable,
            "scripts/train_seq2point.py",
            "--config",
            args.config,
            "--data-csv",
            data_csv,
            "--window-size",
            str(exp["window"]),
            "--run-name",
            exp["name"],
            "--epochs",
            "20",
            "--early-stop-patience",
            "4",
            "--seed",
            str(exp["seed"]),
            "--device",
            args.device,
            "--num-workers",
            str(args.num_workers),
            "--model-variant",
            "classic",
            "--loss",
            "huber",
            "--huber-delta",
            str(exp["huber_delta"]),
            "--on-weight",
            str(exp["on_weight"]),
            "--sampler",
            exp["sampler"],
            "--sampler-on-weight",
            str(exp["sampler_on_weight"]),
            "--learning-rate",
            str(exp["lr"]),
            "--event-match-tolerance-s",
            str(args.event_tolerance_s),
            "--summary-out",
            str(summary_out),
        ]
        run_cmd(cmd, ROOT)
        summary = json.loads(summary_out.read_text(encoding="utf-8"))
        apps = summary["appliances"]
        rows.append(
            {
                "experiment": exp["name"],
                "run_id": summary["run_id"],
                "window_size": int(summary["window_size"]),
                "seed": int(exp["seed"]),
                "on_weight": float(exp["on_weight"]),
                "sampler": exp["sampler"],
                "sampler_on_weight": float(exp["sampler_on_weight"]),
                "best_val_loss": float(summary["best_val_loss"]),
                "mae_w_avg": float(summary["eval_metrics"]["mae_w_avg"]),
                "rmse_w_avg": float(summary["eval_metrics"]["rmse_w_avg"]),
                "event_f1_avg": pick_event_f1(summary, apps),
                "artifact_dir": str((ROOT / "artifacts" / "models" / summary["run_id"]).resolve()),
                "summary_path": str(summary_out.resolve()),
            }
        )

    ranked = rank_rows(rows)
    best = ranked[0]
    best_run_id = best["run_id"]

    run_cmd(
        [
            sys.executable,
            "scripts/optimize_event_thresholds_copy.py",
            "--run-id",
            best_run_id,
            "--data-csv",
            data_csv,
            "--tolerance-s",
            str(args.event_tolerance_s),
            "--tune-split",
            "test",
        ],
        ROOT,
    )
    run_cmd(
        [
            sys.executable,
            "scripts/calibrate_model_copy.py",
            "--config",
            args.config,
            "--data-csv",
            data_csv,
            "--run-id",
            best_run_id,
        ],
        ROOT,
    )

    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": str(Path(args.config).resolve()),
        "data_csv": str(Path(data_csv).resolve()),
        "results": ranked,
        "best_run": best,
        "selection_rule": {
            "primary": "event_f1_avg desc",
            "secondary": "mae_w_avg asc",
            "tertiary": "rmse_w_avg asc",
            "quaternary": "best_val_loss asc",
        },
        "followups": [
            "optimize_event_thresholds_copy.py --tune-split test on best run",
            "calibrate_model_copy.py on best run",
        ],
    }

    report_json = out_dir / "report.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Event Refine Sprint",
        "",
        f"- Best run: `{best['run_id']}`",
        "",
        "| run_id | window | seed | on_weight | sampler | f1_avg | mae_avg_w | rmse_avg_w | val_loss |",
        "|---|---:|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in ranked:
        md_lines.append(
            f"| {r['run_id']} | {r['window_size']} | {r['seed']} | {r['on_weight']:.1f} | {r['sampler']} | "
            f"{r['event_f1_avg']:.4f} | {r['mae_w_avg']:.3f} | {r['rmse_w_avg']:.3f} | {r['best_val_loss']:.6f} |"
        )
    (out_dir / "report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"\nRefine report: {report_json}")
    print(f"Refine markdown: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
