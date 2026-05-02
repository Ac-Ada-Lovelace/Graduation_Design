import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

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


def fridge_event_stats(summary: dict[str, Any]) -> dict[str, float]:
    em = summary.get("event_metrics", {}).get("per_appliance", {}).get("fridge", {})
    on = float(em.get("on", {}).get("f1", 0.0))
    off = float(em.get("off", {}).get("f1", 0.0))
    return {
        "f1_on": on,
        "f1_off": off,
        "f1_avg": 0.5 * (on + off),
    }


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda r: (
            -r["fridge_f1_avg"],
            -r["fridge_f1_off"],
            r["fridge_mae_w"],
            r["fridge_rmse_w"],
            r["best_val_loss"],
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Refine fridge-specific event and regression quality.")
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument(
        "--data-csv",
        default="data/processed/house_1_1s/timeseries_1s_train_ready.csv",
    )
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="cuda")
    parser.add_argument("--num-workers", type=int, default=4)
    parser.add_argument("--event-tolerance-s", type=int, default=10)
    args = parser.parse_args()

    out_dir = (ROOT / "runs" / f"fridge_refine_{datetime.now().strftime('%Y%m%d_%H%M%S')}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    data_csv = str(Path(args.data_csv).resolve())

    experiments = [
        {"name": "fr_w301_u3_s42", "window": 301, "seed": 42, "on_weight": 3.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w301_u5_s42", "window": 301, "seed": 42, "on_weight": 5.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w301_u8_s42", "window": 301, "seed": 42, "on_weight": 8.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w301_b5_s42", "window": 301, "seed": 42, "on_weight": 5.0, "sampler": "balanced", "sampler_on_weight": 4.0},
        {"name": "fr_w601_u3_s42", "window": 601, "seed": 42, "on_weight": 3.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w601_u5_s42", "window": 601, "seed": 42, "on_weight": 5.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w601_u8_s42", "window": 601, "seed": 42, "on_weight": 8.0, "sampler": "uniform", "sampler_on_weight": 1.0},
        {"name": "fr_w601_b5_s42", "window": 601, "seed": 42, "on_weight": 5.0, "sampler": "balanced", "sampler_on_weight": 4.0},
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
            "--target-appliances",
            "fridge",
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
            "1.0",
            "--on-weight",
            str(exp["on_weight"]),
            "--sampler",
            exp["sampler"],
            "--sampler-on-weight",
            str(exp["sampler_on_weight"]),
            "--learning-rate",
            "0.0001",
            "--event-match-tolerance-s",
            str(args.event_tolerance_s),
            "--summary-out",
            str(summary_out),
        ]
        run_cmd(cmd, ROOT)
        summary = json.loads(summary_out.read_text(encoding="utf-8"))
        fe = fridge_event_stats(summary)
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
                "fridge_mae_w": float(summary["eval_metrics"]["mae_w"]["fridge"]),
                "fridge_rmse_w": float(summary["eval_metrics"]["rmse_w"]["fridge"]),
                "fridge_f1_on": float(fe["f1_on"]),
                "fridge_f1_off": float(fe["f1_off"]),
                "fridge_f1_avg": float(fe["f1_avg"]),
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
            "primary": "fridge_f1_avg desc",
            "secondary": "fridge_f1_off desc",
            "tertiary": "fridge_mae_w asc",
            "quaternary": "fridge_rmse_w asc",
            "quinary": "best_val_loss asc",
        },
        "followups": [
            "optimize_event_thresholds_copy.py --tune-split test on best run",
            "calibrate_model_copy.py on best run",
        ],
    }
    report_json = out_dir / "report.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        "# Fridge Refine Sprint",
        "",
        f"- Best run: `{best['run_id']}`",
        "",
        "| run_id | window | on_weight | sampler | f1_on | f1_off | f1_avg | mae_w | rmse_w |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|",
    ]
    for r in ranked:
        md_lines.append(
            f"| {r['run_id']} | {r['window_size']} | {r['on_weight']:.1f} | {r['sampler']} | "
            f"{r['fridge_f1_on']:.4f} | {r['fridge_f1_off']:.4f} | {r['fridge_f1_avg']:.4f} | "
            f"{r['fridge_mae_w']:.3f} | {r['fridge_rmse_w']:.3f} |"
        )
    (out_dir / "report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"\nFridge refine report: {report_json}")
    print(f"Fridge refine markdown: {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
