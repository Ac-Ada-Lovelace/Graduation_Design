from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def registry_path(stage02_root: Path) -> Path:
    return (stage02_root / "integration" / "package_registry.json").resolve()


def load_registry(stage02_root: Path) -> dict[str, Any]:
    path = registry_path(stage02_root)
    if not path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_registry(stage02_root: Path, data: dict[str, Any]) -> Path:
    path = registry_path(stage02_root)
    data = dict(data)
    data["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def get_active_package_ref(stage02_root: Path) -> str:
    data = load_registry(stage02_root)
    ref = str(data.get("active_package", "")).strip()
    if not ref:
        raise ValueError("Registry has no active_package set.")
    return ref


def resolve_package_ref(stage02_root: Path, package_ref: str) -> Path:
    p = Path(package_ref).expanduser()
    if p.is_absolute():
        return p.resolve()
    parts = p.parts
    if parts and parts[0] in {"model", "service", "replay", "ui", "integration"}:
        return (stage02_root / p).resolve()
    # By convention package refs are relative to stage-02/model.
    return (stage02_root / "model" / p).resolve()
