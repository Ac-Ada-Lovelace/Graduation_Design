from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
import zipfile

import numpy as np
import onnxruntime as ort


INTERFACE_VERSION = "nilm_model_interface_v1"
REQUIRED_PACKAGE_FILES = {
    "model.onnx",
    "model_meta.json",
    "normalization.json",
    "postprocess.json",
    "interface_spec.json",
    "package_manifest.json",
}


def _load_json_bytes(raw: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(raw.decode("utf-8-sig"))


def _sha256_bytes(raw: bytes) -> str:
    h = hashlib.sha256()
    h.update(raw)
    return h.hexdigest()


def _require_keys(data: dict[str, Any], keys: list[str], name: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"{name} missing keys: {missing}")


def _hysteresis_states(values: np.ndarray, on_th: float, off_th: float) -> np.ndarray:
    states = np.zeros(len(values), dtype=np.int8)
    state = 0
    for i, v in enumerate(values):
        if state == 0 and v >= on_th:
            state = 1
        elif state == 1 and v <= off_th:
            state = 0
        states[i] = state
    return states


def _enforce_min_durations(states: np.ndarray, min_on_s: int, min_off_s: int) -> np.ndarray:
    out = states.copy()
    n = len(out)
    if n == 0:
        return out

    for _ in range(2):
        i = 0
        while i < n:
            j = i + 1
            while j < n and out[j] == out[i]:
                j += 1
            seg_state = int(out[i])
            seg_len = j - i
            if seg_state == 1 and seg_len < min_on_s:
                out[i:j] = 0
            elif seg_state == 0 and seg_len < min_off_s:
                out[i:j] = 1
            i = j
    return out


def _states_to_events(states: np.ndarray) -> list[tuple[int, str]]:
    if len(states) == 0:
        return []
    events: list[tuple[int, str]] = []
    prev = int(states[0])
    for i in range(1, len(states)):
        cur = int(states[i])
        if prev == 0 and cur == 1:
            events.append((i, "on"))
        elif prev == 1 and cur == 0:
            events.append((i, "off"))
        prev = cur
    return events


def _match_f1(
    true_events: list[tuple[int, str]],
    pred_events: list[tuple[int, str]],
    typ: str,
    tolerance_s: int,
) -> float:
    t_idx = [i for i, k in true_events if k == typ]
    p_idx = [i for i, k in pred_events if k == typ]
    if len(t_idx) == 0 and len(p_idx) == 0:
        return 1.0
    if len(t_idx) == 0 or len(p_idx) == 0:
        return 0.0

    used = set()
    matched = 0
    for ti in t_idx:
        best_j = None
        best_d = 10**9
        for j, pj in enumerate(p_idx):
            if j in used:
                continue
            d = abs(pj - ti)
            if d < best_d:
                best_d = d
                best_j = j
        if best_j is not None and best_d <= tolerance_s:
            used.add(best_j)
            matched += 1
    precision = matched / max(len(p_idx), 1)
    recall = matched / max(len(t_idx), 1)
    return 0.0 if (precision + recall) == 0 else (2 * precision * recall / (precision + recall))


@dataclass
class PackageFiles:
    model_onnx: bytes
    model_meta: dict[str, Any]
    normalization: dict[str, Any]
    postprocess: dict[str, Any]
    interface_spec: dict[str, Any]
    package_manifest: dict[str, Any]


class ModelPackageRuntime:
    def __init__(
        self,
        *,
        package_path: Path,
        files: PackageFiles,
        temp_dir: tempfile.TemporaryDirectory[str],
        session: ort.InferenceSession,
    ) -> None:
        self.package_path = package_path
        self.files = files
        self._temp_dir = temp_dir
        self.session = session

        self.meta = files.model_meta
        self.norm = files.normalization
        self.rules = files.postprocess
        self.spec = files.interface_spec
        self.manifest = files.package_manifest

        self.appliances: list[str] = list(self.meta["appliances"])
        self.window_size: int = int(self.meta["window_size"])
        self.input_name: str = str(self.meta["input_name"])
        self.output_name: str = str(self.meta["output_name"])
        self.sample_period_s: float = float(self.meta["sample_period_s"])

    @classmethod
    def load(
        cls,
        package_zip: str | Path,
        *,
        providers: list[str] | None = None,
        validate_manifest: bool = True,
    ) -> "ModelPackageRuntime":
        package_path = Path(package_zip).resolve()
        if not package_path.exists():
            raise FileNotFoundError(f"Package zip not found: {package_path}")

        with zipfile.ZipFile(package_path, "r") as zf:
            names = set(zf.namelist())
            missing = [n for n in REQUIRED_PACKAGE_FILES if n not in names]
            if missing:
                raise ValueError(f"Package missing required files: {missing}")

            raw_model = zf.read("model.onnx")
            raw_meta = zf.read("model_meta.json")
            raw_norm = zf.read("normalization.json")
            raw_rules = zf.read("postprocess.json")
            raw_spec = zf.read("interface_spec.json")
            raw_manifest = zf.read("package_manifest.json")

            files = PackageFiles(
                model_onnx=raw_model,
                model_meta=_load_json_bytes(raw_meta),
                normalization=_load_json_bytes(raw_norm),
                postprocess=_load_json_bytes(raw_rules),
                interface_spec=_load_json_bytes(raw_spec),
                package_manifest=_load_json_bytes(raw_manifest),
            )

            _require_keys(
                files.model_meta,
                [
                    "model_name",
                    "dataset",
                    "sample_period_s",
                    "window_size",
                    "appliances",
                    "input_name",
                    "output_name",
                    "input_shape",
                    "output_shape",
                ],
                "model_meta.json",
            )
            _require_keys(
                files.normalization,
                ["mains_mean", "mains_std", "target_mean", "target_std"],
                "normalization.json",
            )
            _require_keys(
                files.postprocess,
                ["on_threshold_w", "off_threshold_w", "min_on_seconds", "min_off_seconds"],
                "postprocess.json",
            )
            _require_keys(files.interface_spec, ["interface_version"], "interface_spec.json")
            _require_keys(
                files.package_manifest,
                ["package_format_version", "interface_version", "files"],
                "package_manifest.json",
            )

            interface_version = str(files.interface_spec["interface_version"])
            if interface_version != INTERFACE_VERSION:
                raise ValueError(
                    f"Incompatible interface version: {interface_version} (expected {INTERFACE_VERSION})"
                )
            manifest_iface = str(files.package_manifest["interface_version"])
            if manifest_iface != INTERFACE_VERSION:
                raise ValueError(
                    f"Manifest interface version mismatch: {manifest_iface} (expected {INTERFACE_VERSION})"
                )

            if validate_manifest:
                entries = files.package_manifest.get("files", [])
                entry_map: dict[str, dict[str, Any]] = {}
                for e in entries:
                    p = str(e.get("path", ""))
                    if p:
                        entry_map[p] = e
                for name in names:
                    e = entry_map.get(name)
                    if e is None:
                        continue
                    raw = zf.read(name)
                    expected_bytes = int(e.get("bytes", len(raw)))
                    expected_sha = str(e.get("sha256", ""))
                    if len(raw) != expected_bytes:
                        raise ValueError(f"Manifest bytes mismatch for {name}")
                    if expected_sha and _sha256_bytes(raw) != expected_sha:
                        raise ValueError(f"Manifest sha256 mismatch for {name}")

            temp_dir = tempfile.TemporaryDirectory(prefix="nilm_pkg_")
            temp_path = Path(temp_dir.name)
            for name in names:
                dst = temp_path / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(zf.read(name))

        model_path = temp_path / "model.onnx"
        ort_providers = providers or ["CPUExecutionProvider"]
        session = ort.InferenceSession(str(model_path), providers=ort_providers)
        return cls(package_path=package_path, files=files, temp_dir=temp_dir, session=session)

    def preprocess_mains_windows(self, mains_windows: np.ndarray) -> np.ndarray:
        x = np.asarray(mains_windows, dtype=np.float32)
        if x.ndim != 2:
            raise ValueError(f"mains_windows must be 2D [batch, time], got shape={x.shape}")
        if x.shape[1] != self.window_size:
            raise ValueError(f"window size mismatch: got {x.shape[1]}, expected {self.window_size}")
        mains_mean = float(self.norm["mains_mean"])
        mains_std = float(self.norm["mains_std"])
        if mains_std < 1e-6:
            mains_std = 1.0
        x = (x - mains_mean) / mains_std
        return x[..., np.newaxis].astype(np.float32)

    def denormalize_targets(self, y_norm: np.ndarray) -> np.ndarray:
        y = np.asarray(y_norm, dtype=np.float32)
        means = np.array([self.norm["target_mean"][a] for a in self.appliances], dtype=np.float32)
        stds = np.array([self.norm["target_std"][a] for a in self.appliances], dtype=np.float32)
        return y * stds + means

    def apply_linear_calibration(self, y_w: np.ndarray) -> np.ndarray:
        coeffs = self.rules.get("linear_calibration", {})
        if not isinstance(coeffs, dict) or not coeffs:
            return y_w
        out = y_w.copy()
        for i, app in enumerate(self.appliances):
            row = coeffs.get(app, {})
            a = float(row.get("scale_a", 1.0))
            b = float(row.get("bias_b", 0.0))
            out[:, i] = np.clip(a * out[:, i] + b, a_min=0.0, a_max=None)
        return out

    def infer_windows_watts(self, mains_windows: np.ndarray) -> np.ndarray:
        x = self.preprocess_mains_windows(mains_windows)
        y_norm = self.session.run([self.output_name], {self.input_name: x})[0]
        y_w = self.denormalize_targets(y_norm)
        y_w = self.apply_linear_calibration(y_w)
        return y_w.astype(np.float32)

    def infer_windows_watts_batched(self, mains_windows: np.ndarray, batch_size: int = 4096) -> np.ndarray:
        x = np.asarray(mains_windows, dtype=np.float32)
        if x.ndim != 2:
            raise ValueError(f"mains_windows must be 2D [batch, time], got shape={x.shape}")
        preds: list[np.ndarray] = []
        step = max(1, int(batch_size))
        for i in range(0, len(x), step):
            preds.append(self.infer_windows_watts(x[i : i + step]))
        if not preds:
            return np.empty((0, len(self.appliances)), dtype=np.float32)
        return np.concatenate(preds, axis=0)

    def detect_events(self, series_w: np.ndarray, appliance: str) -> list[tuple[int, str]]:
        if appliance not in self.appliances:
            raise ValueError(f"Unknown appliance: {appliance}")
        on_th = float(self.rules["on_threshold_w"][appliance])
        off_th = float(self.rules["off_threshold_w"][appliance])
        min_on = int(self.rules.get("min_on_seconds", 1))
        min_off = int(self.rules.get("min_off_seconds", 1))
        states = _hysteresis_states(np.asarray(series_w, dtype=np.float32), on_th=on_th, off_th=off_th)
        states = _enforce_min_durations(states, min_on_s=max(1, min_on), min_off_s=max(1, min_off))
        return _states_to_events(states)

    def evaluate_event_f1(
        self,
        y_true_w: np.ndarray,
        y_pred_w: np.ndarray,
        *,
        tolerance_s: int = 10,
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        vals: list[float] = []
        for i, app in enumerate(self.appliances):
            te = self.detect_events(y_true_w[:, i], app)
            pe = self.detect_events(y_pred_w[:, i], app)
            f_on = _match_f1(te, pe, typ="on", tolerance_s=tolerance_s)
            f_off = _match_f1(te, pe, typ="off", tolerance_s=tolerance_s)
            vals.extend([f_on, f_off])
            out[app] = {"f1_on": float(f_on), "f1_off": float(f_off), "f1_avg": float(0.5 * (f_on + f_off))}
        return {
            "per_appliance": out,
            "f1_avg": float(np.mean(np.array(vals, dtype=np.float32))) if vals else 0.0,
        }
