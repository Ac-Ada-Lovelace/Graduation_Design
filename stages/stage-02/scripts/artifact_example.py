import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.artifact import ModelMeta, NormalizationStats, PostprocessRules, save_bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a demo artifact bundle.")
    parser.add_argument("--out", default="artifacts/demo_bundle")
    args = parser.parse_args()

    appliances = ["kettle", "microwave", "fridge"]

    meta = ModelMeta(
        model_name="seq2point-demo",
        dataset="uk-dale",
        sample_period_s=1.0,
        window_size=301,
        appliances=appliances,
        input_name="mains_window",
        output_name="pred_power",
        input_shape=[1, 301, 1],
        output_shape=[1, 3],
    )

    norm = NormalizationStats(
        mains_mean=350.0,
        mains_std=280.0,
        target_mean={name: 0.0 for name in appliances},
        target_std={name: 1.0 for name in appliances},
    )

    rules = PostprocessRules(
        on_threshold_w={"kettle": 1200, "microwave": 700, "fridge": 80},
        off_threshold_w={"kettle": 100, "microwave": 80, "fridge": 50},
        min_on_seconds=10,
        min_off_seconds=10,
    )

    save_bundle(args.out, meta, norm, rules)

    model_placeholder = Path(args.out) / "model.onnx"
    if not model_placeholder.exists():
        model_placeholder.write_bytes(b"PLACEHOLDER_ONNX")

    print(f"Demo bundle created at: {args.out}")


if __name__ == "__main__":
    main()
