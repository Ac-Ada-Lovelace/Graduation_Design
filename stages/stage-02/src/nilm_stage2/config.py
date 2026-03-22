from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    yaml = None


@dataclass
class Stage2Config:
    raw: dict[str, Any]

    @property
    def dataset(self) -> dict[str, Any]:
        return self.raw.get("dataset", {})

    @property
    def experiment(self) -> dict[str, Any]:
        return self.raw.get("experiment", {})


def load_config(path: str | Path) -> Stage2Config:
    config_path = Path(path)
    text = config_path.read_text(encoding="utf-8")

    if config_path.suffix.lower() == ".json":
        data = json.loads(text)
    elif yaml is not None:
        data = yaml.safe_load(text)
    else:
        raise ModuleNotFoundError(
            "PyYAML is not installed. Use a .json config or install requirements.txt"
        )

    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {config_path}")

    return Stage2Config(raw=data)
