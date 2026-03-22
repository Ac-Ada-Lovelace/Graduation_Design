from dataclasses import asdict, dataclass
import json
from pathlib import Path


@dataclass
class ModelMeta:
    model_name: str
    dataset: str
    sample_period_s: float
    window_size: int
    appliances: list[str]
    input_name: str
    output_name: str
    input_shape: list[int]
    output_shape: list[int]


@dataclass
class NormalizationStats:
    mains_mean: float
    mains_std: float
    target_mean: dict[str, float]
    target_std: dict[str, float]


@dataclass
class PostprocessRules:
    on_threshold_w: dict[str, float]
    off_threshold_w: dict[str, float]
    min_on_seconds: int
    min_off_seconds: int


def save_bundle(out_dir: str | Path, meta: ModelMeta, norm: NormalizationStats, rules: PostprocessRules) -> None:
    base = Path(out_dir)
    base.mkdir(parents=True, exist_ok=True)

    (base / "model_meta.json").write_text(
        json.dumps(asdict(meta), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (base / "normalization.json").write_text(
        json.dumps(asdict(norm), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (base / "postprocess.json").write_text(
        json.dumps(asdict(rules), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
