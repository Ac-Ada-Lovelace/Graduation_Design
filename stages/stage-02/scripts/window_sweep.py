import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.config import load_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate window-size sweep plan.")
    parser.add_argument("--config", default="configs/default.json", help="Path to YAML config")
    parser.add_argument("--out", default="runs/window_sweep_plan.json", help="Output plan json")
    args = parser.parse_args()

    cfg = load_config(args.config)
    sample_period_s = float(cfg.dataset.get("model_sample_period_s", 1))
    windows = cfg.experiment.get("window_size_candidates", [])

    if not windows:
        raise ValueError("No window_size_candidates configured")

    rows = []
    for w in windows:
        coverage_seconds = int(w * sample_period_s)
        coverage_minutes = round(coverage_seconds / 60.0, 2)
        run_name = f"w{w}_sp{int(sample_period_s)}"
        command = f"python scripts/train_seq2point.py --config {args.config} --window-size {w} --run-name {run_name}"
        rows.append(
            {
                "window_size": int(w),
                "sample_period_s": sample_period_s,
                "coverage_seconds": coverage_seconds,
                "coverage_minutes": coverage_minutes,
                "run_name": run_name,
                "suggested_command": command,
            }
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Window sweep plan generated:")
    for row in rows:
        print(
            f"- window={row['window_size']}, coverage={row['coverage_minutes']} min, run={row['run_name']}"
        )
    print(f"Saved to: {out_path}")


if __name__ == "__main__":
    main()

