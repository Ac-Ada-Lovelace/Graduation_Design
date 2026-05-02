from __future__ import annotations

from collections import deque
import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field


STAGE02_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_CSV = (
    STAGE02_ROOT
    / "model"
    / "data"
    / "processed"
    / "house_1_1s_kmt"
    / "timeseries_1s_train_ready.csv"
).resolve()
PRESET_INTERVALS_JSON = (
    STAGE02_ROOT / "model" / "configs" / "stage02_acceptance_intervals_kmt.json"
).resolve()
SHOWCASE_PRESETS_JSON = (
    STAGE02_ROOT / "model" / "configs" / "showcase_presets_kmt.json"
).resolve()

if str(STAGE02_ROOT) not in sys.path:
    sys.path.insert(0, str(STAGE02_ROOT))
MODEL_SRC = STAGE02_ROOT / "model" / "src"
if str(MODEL_SRC) not in sys.path:
    sys.path.insert(0, str(MODEL_SRC))

from integration.registry_utils import get_active_package_ref, resolve_package_ref
from nilm_stage2.package_runtime import INTERFACE_VERSION, ModelPackageRuntime


def _normalize_ts(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid timestamp_utc format: {ts}") from exc
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_ts_utc(ts: str) -> pd.Timestamp:
    try:
        return pd.Timestamp(ts, tz="UTC")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Invalid UTC timestamp: {ts}") from exc


def _to_float_list(arr: np.ndarray | list[float]) -> list[float]:
    x = np.asarray(arr, dtype=np.float32)
    return [float(v) for v in x.tolist()]


def _iso_list(ts_series: pd.Series) -> list[str]:
    out: list[str] = []
    for ts in ts_series:
        if isinstance(ts, pd.Timestamp):
            out.append(ts.tz_convert("UTC").isoformat().replace("+00:00", "Z"))
        else:
            out.append(pd.Timestamp(ts, tz="UTC").isoformat().replace("+00:00", "Z"))
    return out


def _load_static_presets() -> list[dict[str, Any]]:
    if not PRESET_INTERVALS_JSON.exists():
        return []
    raw = json.loads(PRESET_INTERVALS_JSON.read_text(encoding="utf-8"))
    intervals = raw.get("intervals")
    if intervals is None:
        return []
    rows = []
    for item in list(intervals):
        rows.append(
            {
                "id": str(item.get("id", "")),
                "label": f"{item.get('id', 'segment')} ({int(item.get('minutes', 0))} min)",
                "start_utc": str(item.get("start_utc", "")),
                "end_utc": str(item.get("end_utc", "")),
                "minutes": int(item.get("minutes", 0)),
                "source": "static",
            }
        )
    return rows


def _load_showcase_presets() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not SHOWCASE_PRESETS_JSON.exists():
        return [], []

    raw = json.loads(SHOWCASE_PRESETS_JSON.read_text(encoding="utf-8"))
    offline_raw = raw.get("offline_presets")
    online_raw = raw.get("online_presets")
    if not isinstance(offline_raw, list):
        offline_raw = []
    if not isinstance(online_raw, list):
        online_raw = []

    def _list_or_empty(v: Any) -> list[Any]:
        return list(v) if isinstance(v, list) else []

    offline: list[dict[str, Any]] = []
    for idx, item in enumerate(offline_raw):
        if not isinstance(item, dict):
            continue
        start_utc = str(item.get("start_utc", "")).strip()
        end_utc = str(item.get("end_utc", "")).strip()
        if not start_utc or not end_utc:
            continue
        offline.append(
            {
                "id": str(item.get("id") or f"manual_offline_{idx+1}"),
                "label": str(item.get("label") or f"Manual Offline #{idx+1}"),
                "start_utc": start_utc,
                "end_utc": end_utc,
                "minutes": int(item.get("minutes", 0) or 0),
                "devices": _list_or_empty(item.get("devices")),
                "tags": _list_or_empty(item.get("tags")),
                "source": "manual_showcase",
            }
        )

    online: list[dict[str, Any]] = []
    for idx, item in enumerate(online_raw):
        if not isinstance(item, dict):
            continue
        start_utc = str(item.get("start_utc", "")).strip()
        if not start_utc:
            continue
        end_utc_raw = item.get("end_utc")
        end_utc = str(end_utc_raw).strip() if isinstance(end_utc_raw, str) else ""
        online.append(
            {
                "id": str(item.get("id") or f"manual_online_{idx+1}"),
                "label": str(item.get("label") or f"Manual Online #{idx+1}"),
                "start_utc": start_utc,
                "end_utc": end_utc,
                "devices": _list_or_empty(item.get("devices")),
                "tags": _list_or_empty(item.get("tags")),
                "speed_options": _list_or_empty(item.get("speed_options")) or [1, 5, 20, 50],
                "source": "manual_showcase",
            }
        )

    return offline, online


def _match_events_with_tolerance(
    true_events: list[tuple[int, str]],
    pred_events: list[tuple[int, str]],
    *,
    typ: str,
    tolerance_s: int,
) -> dict[str, Any]:
    t_idx = [i for i, k in true_events if k == typ]
    p_idx = [i for i, k in pred_events if k == typ]

    if len(t_idx) == 0 and len(p_idx) == 0:
        return {
            "pairs": [],
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "true_count": 0,
            "pred_count": 0,
            "matched_count": 0,
            "mean_abs_delta_s": 0.0,
            "p95_abs_delta_s": 0.0,
        }
    if len(t_idx) == 0 or len(p_idx) == 0:
        return {
            "pairs": [],
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "true_count": len(t_idx),
            "pred_count": len(p_idx),
            "matched_count": 0,
            "mean_abs_delta_s": 0.0,
            "p95_abs_delta_s": 0.0,
        }

    used_pred: set[int] = set()
    pairs: list[dict[str, Any]] = []
    for ti in t_idx:
        best_j = None
        best_d = 10**9
        for j, pj in enumerate(p_idx):
            if j in used_pred:
                continue
            d = abs(pj - ti)
            if d < best_d:
                best_d = d
                best_j = j
        if best_j is not None and best_d <= tolerance_s:
            used_pred.add(best_j)
            pj = p_idx[best_j]
            pairs.append(
                {
                    "true_index": int(ti),
                    "pred_index": int(pj),
                    "delta_s": int(pj - ti),
                    "abs_delta_s": int(abs(pj - ti)),
                    "type": typ,
                }
            )

    matched = len(pairs)
    precision = matched / max(len(p_idx), 1)
    recall = matched / max(len(t_idx), 1)
    f1 = 0.0 if (precision + recall) == 0 else (2 * precision * recall / (precision + recall))
    abs_deltas = np.array([p["abs_delta_s"] for p in pairs], dtype=np.float32) if pairs else np.array([], dtype=np.float32)
    mean_abs = float(abs_deltas.mean()) if len(abs_deltas) else 0.0
    p95_abs = float(np.percentile(abs_deltas, 95)) if len(abs_deltas) else 0.0
    return {
        "pairs": pairs,
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "true_count": int(len(t_idx)),
        "pred_count": int(len(p_idx)),
        "matched_count": int(matched),
        "mean_abs_delta_s": mean_abs,
        "p95_abs_delta_s": p95_abs,
    }


def _build_downsample_indices(
    *,
    n: int,
    series_map: dict[str, np.ndarray],
    must_keep: set[int],
    target_points: int,
) -> list[int]:
    if n <= target_points:
        return list(range(n))

    keep = {0, n - 1}
    keep.update(i for i in must_keep if 0 <= i < n)
    if len(keep) >= target_points:
        base = sorted(keep)
        step = max(1, int(np.ceil(len(base) / target_points)))
        return base[::step][:target_points]

    remaining = target_points - len(keep)
    bucket_count = max(1, remaining // 3)
    bucket_edges = np.linspace(0, n, num=bucket_count + 1, dtype=np.int32)
    keys = list(series_map.keys())
    for b in range(bucket_count):
        s = int(bucket_edges[b])
        e = int(bucket_edges[b + 1])
        if e <= s:
            continue
        keep.add(e - 1)
        for k in keys:
            arr = series_map[k]
            seg = arr[s:e]
            if len(seg) == 0:
                continue
            imin = int(np.argmin(seg)) + s
            imax = int(np.argmax(seg)) + s
            keep.add(imin)
            keep.add(imax)

    idx = sorted(i for i in keep if 0 <= i < n)
    if len(idx) > target_points:
        step = max(1, int(np.ceil(len(idx) / target_points)))
        idx = idx[::step][:target_points]
    return idx


class StartSessionRequest(BaseModel):
    package_zip: str | None = Field(
        default=None,
        description="Path to model package zip. If omitted, use registry active package.",
    )
    providers: list[str] | None = Field(default=None, description="ONNX providers")
    validate_manifest: bool = Field(default=True)


class IngestRequest(BaseModel):
    timestamp_utc: str = Field(..., description="ISO8601 timestamp in UTC")
    mains_w: float = Field(..., description="Mains active power in watts")


class OfflineInferRequest(BaseModel):
    start_utc: str = Field(..., description="UTC start timestamp")
    end_utc: str = Field(..., description="UTC end timestamp")
    data_csv: str | None = Field(default=None, description="Optional data csv path")
    package_zip: str | None = Field(default=None, description="Optional package override")
    event_tolerance_s: int = Field(default=10)
    batch_size: int = Field(default=4096)
    max_points: int = Field(default=54000, description="Absolute guard on full interval points")
    target_points: int = Field(default=1200, description="Returned chart points after downsampling")


class OnlineStartRequest(BaseModel):
    start_utc: str | None = Field(default=None, description="Optional replay start timestamp")
    end_utc: str | None = Field(default=None, description="Optional replay end timestamp")
    data_csv: str | None = Field(default=None)
    package_zip: str | None = Field(default=None)
    speed: float = Field(default=20.0, description="Replay speed multiplier (>0)")
    max_rows: int = Field(default=0, description="Stop after N rows (0 means no limit)")


@dataclass
class SessionRuntime:
    runtime: ModelPackageRuntime
    package_zip: str
    mains_buffer: deque[float] = field(init=False)
    ingest_count: int = 0
    pred_count: int = 0
    pred_history: dict[str, list[float]] = field(init=False)
    pred_timestamps: list[str] = field(default_factory=list)
    event_cursor: dict[str, int] = field(init=False)
    latest: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.mains_buffer = deque(maxlen=self.runtime.window_size)
        self.pred_history = {a: [] for a in self.runtime.appliances}
        self.event_cursor = {a: 0 for a in self.runtime.appliances}
        self.latest = {
            "ready": False,
            "timestamp_utc": None,
            "pred_w": {a: 0.0 for a in self.runtime.appliances},
            "events": [],
            "model_version": Path(self.package_zip).name,
            "buffer_fill": 0,
            "window_size": int(self.runtime.window_size),
            "ingest_count": 0,
            "pred_count": 0,
        }

    def reset(self) -> None:
        with self._lock:
            self.mains_buffer.clear()
            self.ingest_count = 0
            self.pred_count = 0
            self.pred_timestamps.clear()
            for app in self.runtime.appliances:
                self.pred_history[app].clear()
                self.event_cursor[app] = 0
            self.latest = {
                "ready": False,
                "timestamp_utc": None,
                "pred_w": {a: 0.0 for a in self.runtime.appliances},
                "events": [],
                "model_version": Path(self.package_zip).name,
                "buffer_fill": 0,
                "window_size": int(self.runtime.window_size),
                "ingest_count": 0,
                "pred_count": 0,
            }

    def ingest(self, timestamp_utc: str, mains_w: float) -> dict[str, Any]:
        ts = _normalize_ts(timestamp_utc)
        with self._lock:
            self.ingest_count += 1
            self.mains_buffer.append(float(mains_w))

            if len(self.mains_buffer) < self.runtime.window_size:
                self.latest.update(
                    {
                        "ready": False,
                        "timestamp_utc": ts,
                        "events": [],
                        "buffer_fill": int(len(self.mains_buffer)),
                        "ingest_count": int(self.ingest_count),
                        "pred_count": int(self.pred_count),
                    }
                )
                return copy.deepcopy(self.latest)

            window = np.asarray(self.mains_buffer, dtype=np.float32)[np.newaxis, :]
            pred = self.runtime.infer_windows_watts(window)[0]
            pred_map = {
                app: float(max(pred[i], 0.0))
                for i, app in enumerate(self.runtime.appliances)
            }

            self.pred_timestamps.append(ts)
            for app in self.runtime.appliances:
                self.pred_history[app].append(float(pred_map[app]))

            new_events: list[dict[str, Any]] = []
            for app in self.runtime.appliances:
                series = np.asarray(self.pred_history[app], dtype=np.float32)
                events = self.runtime.detect_events(series, appliance=app)
                cursor = self.event_cursor[app]
                if cursor < len(events):
                    for idx, typ in events[cursor:]:
                        evt_ts = self.pred_timestamps[idx] if idx < len(self.pred_timestamps) else ts
                        new_events.append(
                            {
                                "device": app,
                                "type": typ,
                                "index": int(idx),
                                "timestamp_utc": evt_ts,
                            }
                        )
                    self.event_cursor[app] = len(events)

            self.pred_count += 1
            self.latest = {
                "ready": True,
                "timestamp_utc": ts,
                "pred_w": pred_map,
                "events": new_events,
                "model_version": Path(self.package_zip).name,
                "buffer_fill": int(len(self.mains_buffer)),
                "window_size": int(self.runtime.window_size),
                "ingest_count": int(self.ingest_count),
                "pred_count": int(self.pred_count),
            }
            return copy.deepcopy(self.latest)

    def snapshot_latest(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self.latest)


class ServiceState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: SessionRuntime | None = None

    def start_session(
        self,
        *,
        package_zip: str | None,
        providers: list[str] | None,
        validate_manifest: bool,
    ) -> SessionRuntime:
        package_ref = package_zip.strip() if isinstance(package_zip, str) and package_zip.strip() else ""
        if not package_ref:
            package_ref = get_active_package_ref(STAGE02_ROOT)
        pkg_path = resolve_package_ref(STAGE02_ROOT, package_ref)
        runtime = ModelPackageRuntime.load(
            pkg_path,
            providers=providers,
            validate_manifest=validate_manifest,
        )
        session = SessionRuntime(runtime=runtime, package_zip=str(pkg_path))
        with self._lock:
            self._session = session
        return session

    def ensure_session(self) -> SessionRuntime:
        with self._lock:
            s = self._session
        if s is not None:
            return s
        return self.start_session(package_zip=None, providers=None, validate_manifest=True)

    def require_session(self) -> SessionRuntime:
        with self._lock:
            s = self._session
        if s is None:
            raise HTTPException(status_code=400, detail="No active session. Call /session/start first.")
        return s

    def has_session(self) -> bool:
        with self._lock:
            return self._session is not None


_DATAFRAME_CACHE: dict[str, pd.DataFrame] = {}
_DATAFRAME_LOCK = threading.Lock()


def _resolve_data_csv(path: str | None) -> Path:
    if path and path.strip():
        p = Path(path).expanduser()
        if not p.is_absolute():
            p = (STAGE02_ROOT / p).resolve()
    else:
        p = DEFAULT_DATA_CSV
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"data csv not found: {p}")
    return p.resolve()


def _load_dataset_frame(csv_path: Path, appliances: list[str]) -> pd.DataFrame:
    key = str(csv_path)
    with _DATAFRAME_LOCK:
        cached = _DATAFRAME_CACHE.get(key)
    if cached is not None:
        missing = [f"{a}_w" for a in appliances if f"{a}_w" not in cached.columns]
        if not missing:
            return cached

    needed = ["timestamp_utc", "mains_w", *[f"{a}_w" for a in appliances]]
    df = pd.read_csv(csv_path)
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise HTTPException(status_code=422, detail=f"csv missing columns: {missing}")
    df = df[needed].dropna().copy()
    if df.empty:
        raise HTTPException(status_code=422, detail=f"csv has no valid rows: {csv_path}")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    df = df.sort_values("timestamp_utc").reset_index(drop=True)
    with _DATAFRAME_LOCK:
        _DATAFRAME_CACHE[key] = df
    return df


def _build_dynamic_presets(
    *,
    runtime: ModelPackageRuntime,
    df: pd.DataFrame,
    per_appliance_limit: int = 3,
) -> list[dict[str, Any]]:
    presets: list[dict[str, Any]] = []
    for app in runtime.appliances:
        vals = df[f"{app}_w"].to_numpy(dtype=np.float32)
        events = runtime.detect_events(vals, appliance=app)
        on_idx = [i for i, typ in events if typ == "on"]
        off_idx = [i for i, typ in events if typ == "off"]
        if not on_idx or not off_idx:
            continue

        # Pair each on with next off to form run cycles.
        cycles: list[tuple[int, int, int]] = []
        j = 0
        for s in on_idx:
            while j < len(off_idx) and off_idx[j] <= s:
                j += 1
            if j >= len(off_idx):
                break
            e = off_idx[j]
            dur = e - s
            if dur < 5:
                continue
            cycles.append((s, e, dur))
            j += 1
        if not cycles:
            continue

        cycles_sorted = sorted(cycles, key=lambda x: x[2])
        picks = [cycles_sorted[0], cycles_sorted[len(cycles_sorted) // 2], cycles_sorted[-1]]
        # Deduplicate by start index while preserving order.
        seen: set[int] = set()
        selected: list[tuple[int, int, int]] = []
        for c in picks:
            if c[0] in seen:
                continue
            seen.add(c[0])
            selected.append(c)
        selected = selected[: max(1, per_appliance_limit)]

        for rank, (s, e, dur) in enumerate(selected, start=1):
            pad = max(30, min(300, dur // 3))
            ss = max(0, s - pad)
            ee = min(len(df) - 1, e + pad)
            st = df["timestamp_utc"].iloc[ss].tz_convert("UTC").isoformat().replace("+00:00", "Z")
            et = df["timestamp_utc"].iloc[ee].tz_convert("UTC").isoformat().replace("+00:00", "Z")
            tag = "short" if rank == 1 else ("median" if rank == 2 else "long")
            presets.append(
                {
                    "id": f"dyn_{app}_{tag}_{rank}",
                    "label": f"{app} {tag} cycle ({int((ee-ss+1)/60)} min)",
                    "start_utc": st,
                    "end_utc": et,
                    "minutes": int(max(1, (ee - ss + 1) // 60)),
                    "devices": [app],
                    "tags": ["dynamic", "cycle", tag],
                    "source": "dynamic",
                }
            )
    return presets


def _events_to_json(
    events: list[tuple[int, str]],
    ts_list: list[str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, typ in events:
        ts = ts_list[idx] if 0 <= idx < len(ts_list) else None
        out.append({"index": int(idx), "type": typ, "timestamp_utc": ts})
    return out


def _build_presets(
    *,
    runtime: ModelPackageRuntime,
    df: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manual_offline, manual_online = _load_showcase_presets()
    if manual_offline:
        offline = manual_offline
        online = manual_online
        if not online:
            online = [
                {
                    "id": f"start_{p.get('id', 'x')}",
                    "label": f"{p.get('label', p.get('id', 'segment'))} [start]",
                    "start_utc": p.get("start_utc"),
                    "end_utc": p.get("end_utc"),
                    "devices": p.get("devices", []),
                    "tags": p.get("tags", []),
                    "speed_options": [1, 5, 20, 50],
                    "source": "manual_showcase_derived",
                }
                for p in offline
            ]
        return offline, online

    static_presets = _load_static_presets()
    dynamic_presets = _build_dynamic_presets(runtime=runtime, df=df, per_appliance_limit=3)
    offline_all = static_presets + dynamic_presets
    dedup: dict[tuple[str, str], dict[str, Any]] = {}
    for p in offline_all:
        key = (str(p.get("start_utc", "")), str(p.get("end_utc", "")))
        dedup[key] = p
    offline = list(dedup.values())
    offline = sorted(offline, key=lambda x: str(x.get("start_utc", "")))

    online: list[dict[str, Any]] = []
    for p in offline:
        online.append(
            {
                "id": f"start_{p.get('id', 'x')}",
                "label": f"{p.get('label', p.get('id', 'segment'))} [start]",
                "start_utc": p.get("start_utc"),
                "end_utc": p.get("end_utc"),
                "devices": p.get("devices", []),
                "tags": p.get("tags", []),
                "speed_options": [1, 5, 20, 50],
                "source": p.get("source", "derived"),
            }
        )
    return offline, online


def _offline_infer(
    *,
    session: SessionRuntime,
    data_csv: Path,
    start_utc: str,
    end_utc: str,
    batch_size: int,
    event_tolerance_s: int,
    max_points: int,
    target_points: int,
) -> dict[str, Any]:
    runtime = session.runtime
    df = _load_dataset_frame(data_csv, runtime.appliances)

    start = _parse_ts_utc(start_utc)
    end = _parse_ts_utc(end_utc)
    if end <= start:
        raise HTTPException(status_code=422, detail="end_utc must be greater than start_utc")

    margin = int(runtime.window_size // 2 + 2)
    ext_start = start - pd.Timedelta(seconds=margin)
    ext_end = end + pd.Timedelta(seconds=margin)

    sub = df[(df["timestamp_utc"] >= ext_start) & (df["timestamp_utc"] <= ext_end)].copy()
    if len(sub) < runtime.window_size:
        raise HTTPException(
            status_code=422,
            detail=f"interval context has insufficient rows for window_size={runtime.window_size}",
        )

    mains = sub["mains_w"].to_numpy(dtype=np.float32)
    x = np.lib.stride_tricks.sliding_window_view(mains, runtime.window_size).astype(np.float32)
    y_pred = runtime.infer_windows_watts_batched(x, batch_size=max(1, int(batch_size)))

    center = runtime.window_size // 2
    rows = len(y_pred)
    pred_df = pd.DataFrame(
        {
            "timestamp_utc": sub["timestamp_utc"].iloc[center : center + rows].reset_index(drop=True),
            "mains_w": sub["mains_w"].iloc[center : center + rows].to_numpy(dtype=np.float32),
        }
    )
    for i, app in enumerate(runtime.appliances):
        pred_df[f"true_{app}_w"] = sub[f"{app}_w"].iloc[center : center + rows].to_numpy(dtype=np.float32)
        pred_df[f"pred_{app}_w"] = y_pred[:, i]

    seg = pred_df[(pred_df["timestamp_utc"] >= start) & (pred_df["timestamp_utc"] <= end)].reset_index(drop=True)
    if seg.empty:
        raise HTTPException(status_code=422, detail="selected interval has no aligned prediction rows")
    full_n = int(len(seg))
    if full_n > int(max_points):
        raise HTTPException(
            status_code=422,
            detail=f"selected interval has {full_n} points > max_points={max_points}, please narrow interval",
        )

    y_true = np.stack(
        [seg[f"true_{a}_w"].to_numpy(dtype=np.float32) for a in runtime.appliances],
        axis=1,
    )
    y_hat = np.stack(
        [seg[f"pred_{a}_w"].to_numpy(dtype=np.float32) for a in runtime.appliances],
        axis=1,
    )
    ae = np.abs(y_hat - y_true)
    se = (y_hat - y_true) ** 2
    diff = y_hat - y_true
    mae = ae.mean(axis=0)
    rmse = np.sqrt(se.mean(axis=0))
    event_metrics = runtime.evaluate_event_f1(y_true, y_hat, tolerance_s=max(1, int(event_tolerance_s)))

    per_app = {}
    for i, app in enumerate(runtime.appliances):
        true_events = runtime.detect_events(y_true[:, i], appliance=app)
        pred_events = runtime.detect_events(y_hat[:, i], appliance=app)
        m_on = _match_events_with_tolerance(
            true_events,
            pred_events,
            typ="on",
            tolerance_s=max(1, int(event_tolerance_s)),
        )
        m_off = _match_events_with_tolerance(
            true_events,
            pred_events,
            typ="off",
            tolerance_s=max(1, int(event_tolerance_s)),
        )
        abs_delta_pool = np.array(
            [*([p["abs_delta_s"] for p in m_on["pairs"]]), *([p["abs_delta_s"] for p in m_off["pairs"]])],
            dtype=np.float32,
        )
        mean_abs_delta = float(abs_delta_pool.mean()) if len(abs_delta_pool) else 0.0
        p95_abs_delta = float(np.percentile(abs_delta_pool, 95)) if len(abs_delta_pool) else 0.0
        per_app[app] = {
            "mae_w": float(mae[i]),
            "rmse_w": float(rmse[i]),
            "mean_diff_w": float(diff[:, i].mean()),
            "max_abs_diff_w": float(np.abs(diff[:, i]).max()),
            "event_mean_abs_delta_s": mean_abs_delta,
            "event_p95_abs_delta_s": p95_abs_delta,
            "event_on": m_on,
            "event_off": m_off,
        }

    ts_list_full = _iso_list(seg["timestamp_utc"])
    events_payload: dict[str, Any] = {}
    must_keep: set[int] = {0, max(0, full_n - 1)}
    for i, app in enumerate(runtime.appliances):
        true_events = runtime.detect_events(y_true[:, i], appliance=app)
        pred_events = runtime.detect_events(y_hat[:, i], appliance=app)
        must_keep.update([idx for idx, _ in true_events])
        must_keep.update([idx for idx, _ in pred_events])
        events_payload[app] = {
            "true": _events_to_json(true_events, ts_list_full),
            "pred": _events_to_json(pred_events, ts_list_full),
            "true_count": int(len(true_events)),
            "pred_count": int(len(pred_events)),
        }

    series_map: dict[str, np.ndarray] = {"mains_w": seg["mains_w"].to_numpy(dtype=np.float32)}
    for app in runtime.appliances:
        series_map[f"true_{app}_w"] = seg[f"true_{app}_w"].to_numpy(dtype=np.float32)
        series_map[f"pred_{app}_w"] = seg[f"pred_{app}_w"].to_numpy(dtype=np.float32)

    target = max(200, int(target_points))
    sample_idx = _build_downsample_indices(
        n=full_n,
        series_map=series_map,
        must_keep=must_keep,
        target_points=target,
    )
    sampled = seg.iloc[sample_idx].reset_index(drop=True)
    ts_list = _iso_list(sampled["timestamp_utc"])

    return {
        "config": {
            "data_csv": str(data_csv),
            "start_utc": start.tz_convert("UTC").isoformat().replace("+00:00", "Z"),
            "end_utc": end.tz_convert("UTC").isoformat().replace("+00:00", "Z"),
            "window_size": int(runtime.window_size),
            "sample_period_s": float(runtime.sample_period_s),
            "appliances": list(runtime.appliances),
            "event_tolerance_s": int(event_tolerance_s),
            "point_count_full": full_n,
            "point_count_returned": int(len(sampled)),
            "downsample_applied": bool(full_n > len(sampled)),
        },
        "metrics": {
            "mae_avg_w": float(np.mean(mae)),
            "rmse_avg_w": float(np.mean(rmse)),
            "mean_diff_avg_w": float(diff.mean()),
            "max_abs_diff_w": float(np.abs(diff).max()),
            "per_appliance": per_app,
            "event": event_metrics,
        },
        "series": {
            "timestamp_utc": ts_list,
            "mains_w": _to_float_list(sampled["mains_w"].to_numpy(dtype=np.float32)),
            "true_w": {
                app: _to_float_list(sampled[f"true_{app}_w"].to_numpy(dtype=np.float32))
                for app in runtime.appliances
            },
            "pred_w": {
                app: _to_float_list(sampled[f"pred_{app}_w"].to_numpy(dtype=np.float32))
                for app in runtime.appliances
            },
            "diff_w": {
                app: _to_float_list(
                    (sampled[f"pred_{app}_w"].to_numpy(dtype=np.float32) - sampled[f"true_{app}_w"].to_numpy(dtype=np.float32))
                )
                for app in runtime.appliances
            },
        },
        "events": events_payload,
    }


class OnlineReplayController:
    def __init__(self, state: ServiceState) -> None:
        self._state = state
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event: threading.Event | None = None
        self._running = False
        self._sent_rows = 0
        self._speed = 0.0
        self._start_utc = ""
        self._end_utc = ""
        self._max_rows = 0
        self._data_csv = ""
        self._last_error = ""
        self._history_ts: deque[str] = deque(maxlen=2400)
        self._history_true: dict[str, deque[float]] = {}
        self._history_pred: dict[str, deque[float]] = {}

    def _init_history(self, appliances: list[str]) -> None:
        self._history_ts = deque(maxlen=2400)
        self._history_true = {a: deque(maxlen=2400) for a in appliances}
        self._history_pred = {a: deque(maxlen=2400) for a in appliances}

    def start(
        self,
        *,
        session: SessionRuntime,
        data_csv: Path,
        start_utc: str | None,
        end_utc: str | None,
        speed: float,
        max_rows: int,
    ) -> None:
        if speed <= 0:
            raise HTTPException(status_code=422, detail="speed must be > 0")
        with self._lock:
            if self._running:
                raise HTTPException(status_code=409, detail="online replay is already running")
            self._running = True
            self._sent_rows = 0
            self._speed = float(speed)
            self._start_utc = start_utc or ""
            self._end_utc = end_utc or ""
            self._max_rows = int(max_rows)
            self._data_csv = str(data_csv)
            self._last_error = ""
            self._stop_event = threading.Event()
            self._init_history(session.runtime.appliances)

        th = threading.Thread(
            target=self._worker,
            kwargs={
                "session": session,
                "data_csv": data_csv,
                "start_utc": start_utc,
                "end_utc": end_utc,
                "speed": float(speed),
                "max_rows": int(max_rows),
            },
            daemon=True,
        )
        with self._lock:
            self._thread = th
        th.start()

    def _worker(
        self,
        *,
        session: SessionRuntime,
        data_csv: Path,
        start_utc: str | None,
        end_utc: str | None,
        speed: float,
        max_rows: int,
    ) -> None:
        stop_event: threading.Event | None
        with self._lock:
            stop_event = self._stop_event
        try:
            df = _load_dataset_frame(data_csv, session.runtime.appliances)
            if start_utc:
                s = _parse_ts_utc(start_utc)
                df = df[df["timestamp_utc"] >= s]
            if end_utc:
                e = _parse_ts_utc(end_utc)
                df = df[df["timestamp_utc"] <= e]
            if df.empty:
                raise RuntimeError("No rows available for selected online replay interval.")

            prev_ts: pd.Timestamp | None = None
            sent = 0
            for row in df.itertuples(index=False):
                if stop_event is not None and stop_event.is_set():
                    break

                ts = row.timestamp_utc
                ts_iso = ts.tz_convert("UTC").isoformat().replace("+00:00", "Z")
                out = session.ingest(timestamp_utc=ts_iso, mains_w=float(row.mains_w))

                sent += 1
                with self._lock:
                    self._sent_rows = sent

                if out.get("ready"):
                    with self._lock:
                        self._history_ts.append(ts_iso)
                        for app in session.runtime.appliances:
                            self._history_true[app].append(float(getattr(row, f"{app}_w")))
                            self._history_pred[app].append(float(out["pred_w"][app]))

                if max_rows > 0 and sent >= max_rows:
                    break

                if prev_ts is not None:
                    delta_s = max((ts - prev_ts).total_seconds(), 0.0)
                    sleep_s = delta_s / speed
                    if sleep_s > 0:
                        time.sleep(sleep_s)
                prev_ts = ts
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._last_error = str(exc)
        finally:
            with self._lock:
                self._running = False

    def stop(self) -> None:
        with self._lock:
            if self._stop_event is not None:
                self._stop_event.set()

    def status(self, session: SessionRuntime) -> dict[str, Any]:
        with self._lock:
            running = bool(self._running)
            sent_rows = int(self._sent_rows)
            speed = float(self._speed)
            start_utc = self._start_utc
            end_utc = self._end_utc
            max_rows = int(self._max_rows)
            data_csv = self._data_csv
            last_error = self._last_error
            ts = list(self._history_ts)
            true_hist = {k: [float(v) for v in vals] for k, vals in self._history_true.items()}
            pred_hist = {k: [float(v) for v in vals] for k, vals in self._history_pred.items()}

        metrics: dict[str, Any] = {}
        true_stream: list[dict[str, Any]] = []
        pred_stream: list[dict[str, Any]] = []
        if ts and true_hist and pred_hist:
            apps = session.runtime.appliances
            y_true = np.stack([np.asarray(true_hist[a], dtype=np.float32) for a in apps], axis=1)
            y_hat = np.stack([np.asarray(pred_hist[a], dtype=np.float32) for a in apps], axis=1)
            diff = y_hat - y_true
            mae = np.abs(y_hat - y_true).mean(axis=0)
            rmse = np.sqrt(((y_hat - y_true) ** 2).mean(axis=0))
            metrics = {
                "mae_avg_w": float(np.mean(mae)),
                "rmse_avg_w": float(np.mean(rmse)),
                "mean_diff_avg_w": float(diff.mean()),
                "max_abs_diff_w": float(np.abs(diff).max()),
                "per_appliance": {
                    app: {
                        "mae_w": float(mae[i]),
                        "rmse_w": float(rmse[i]),
                        "mean_diff_w": float(diff[:, i].mean()),
                        "max_abs_diff_w": float(np.abs(diff[:, i]).max()),
                    }
                    for i, app in enumerate(apps)
                },
            }
            for app in apps:
                t_ev = session.runtime.detect_events(np.asarray(true_hist[app], dtype=np.float32), appliance=app)
                p_ev = session.runtime.detect_events(np.asarray(pred_hist[app], dtype=np.float32), appliance=app)
                for idx, typ in t_ev:
                    tts = ts[idx] if 0 <= idx < len(ts) else None
                    true_stream.append({"device": app, "type": typ, "index": int(idx), "timestamp_utc": tts})
                for idx, typ in p_ev:
                    pts = ts[idx] if 0 <= idx < len(ts) else None
                    pred_stream.append({"device": app, "type": typ, "index": int(idx), "timestamp_utc": pts})
            true_stream.sort(key=lambda x: x.get("timestamp_utc") or "")
            pred_stream.sort(key=lambda x: x.get("timestamp_utc") or "")

        return {
            "running": running,
            "sent_rows": sent_rows,
            "speed": speed,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "max_rows": max_rows,
            "data_csv": data_csv,
            "last_error": last_error,
            "latest": session.snapshot_latest(),
            "history": {
                "timestamp_utc": ts,
                "true_w": true_hist,
                "pred_w": pred_hist,
            },
            "metrics": metrics,
            "event_stream": {
                "true": true_stream[-100:],
                "pred": pred_stream[-100:],
            },
        }


state = ServiceState()
online = OnlineReplayController(state)
app = FastAPI(title="Stage-02 NILM Service", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Demo mode.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, Any]:
    active_ref = ""
    try:
        active_ref = get_active_package_ref(STAGE02_ROOT)
    except Exception:  # noqa: BLE001
        active_ref = ""
    return {
        "status": "ok",
        "interface_version": INTERFACE_VERSION,
        "has_session": state.has_session(),
        "registry_active_package": active_ref,
    }


@app.post("/session/start")
def session_start(req: StartSessionRequest) -> dict[str, Any]:
    try:
        s = state.start_session(
            package_zip=req.package_zip,
            providers=req.providers,
            validate_manifest=bool(req.validate_manifest),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Failed to start session: {exc}") from exc

    return {
        "message": "session started",
        "package_zip": s.package_zip,
        "model_name": s.runtime.meta["model_name"],
        "appliances": s.runtime.appliances,
        "window_size": int(s.runtime.window_size),
        "sample_period_s": float(s.runtime.sample_period_s),
        "providers": s.runtime.session.get_providers(),
    }


@app.post("/session/reset")
def session_reset() -> dict[str, Any]:
    s = state.require_session()
    s.reset()
    return {"message": "session reset", "window_size": int(s.runtime.window_size)}


@app.post("/session/ingest")
def session_ingest(req: IngestRequest) -> dict[str, Any]:
    s = state.require_session()
    return s.ingest(timestamp_utc=req.timestamp_utc, mains_w=float(req.mains_w))


@app.get("/session/latest")
def session_latest() -> dict[str, Any]:
    s = state.require_session()
    return s.snapshot_latest()


@app.get("/api/meta")
def api_meta(data_csv: str | None = None) -> dict[str, Any]:
    s = state.ensure_session()
    csv_path = _resolve_data_csv(data_csv)
    df = _load_dataset_frame(csv_path, s.runtime.appliances)
    offline_presets, online_presets = _build_presets(runtime=s.runtime, df=df)
    return {
        "data_csv": str(csv_path),
        "data_range": {
            "start_utc": df["timestamp_utc"].iloc[0].tz_convert("UTC").isoformat().replace("+00:00", "Z"),
            "end_utc": df["timestamp_utc"].iloc[-1].tz_convert("UTC").isoformat().replace("+00:00", "Z"),
            "rows": int(len(df)),
        },
        "appliances": list(s.runtime.appliances),
        "window_size": int(s.runtime.window_size),
        "sample_period_s": float(s.runtime.sample_period_s),
        "presets": offline_presets,
        "offline_presets": offline_presets,
        "online_presets": online_presets,
    }


@app.get("/api/presets/offline")
def api_presets_offline(data_csv: str | None = None) -> dict[str, Any]:
    s = state.ensure_session()
    csv_path = _resolve_data_csv(data_csv)
    df = _load_dataset_frame(csv_path, s.runtime.appliances)
    offline_presets, _ = _build_presets(runtime=s.runtime, df=df)
    return {
        "data_csv": str(csv_path),
        "count": int(len(offline_presets)),
        "presets": offline_presets,
    }


@app.get("/api/presets/online")
def api_presets_online(data_csv: str | None = None) -> dict[str, Any]:
    s = state.ensure_session()
    csv_path = _resolve_data_csv(data_csv)
    df = _load_dataset_frame(csv_path, s.runtime.appliances)
    _, online_presets = _build_presets(runtime=s.runtime, df=df)
    return {
        "data_csv": str(csv_path),
        "count": int(len(online_presets)),
        "presets": online_presets,
    }


@app.post("/api/offline/infer")
def api_offline_infer(req: OfflineInferRequest) -> dict[str, Any]:
    try:
        s = state.ensure_session()
        if req.package_zip and req.package_zip.strip():
            s = state.start_session(
                package_zip=req.package_zip,
                providers=None,
                validate_manifest=True,
            )
        csv_path = _resolve_data_csv(req.data_csv)
        result = _offline_infer(
            session=s,
            data_csv=csv_path,
            start_utc=req.start_utc,
            end_utc=req.end_utc,
            batch_size=max(1, int(req.batch_size)),
            event_tolerance_s=max(1, int(req.event_tolerance_s)),
            max_points=max(100, int(req.max_points)),
            target_points=max(200, int(req.target_points)),
        )
        return result
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"offline inference failed: {exc}") from exc


@app.post("/api/online/start")
def api_online_start(req: OnlineStartRequest) -> dict[str, Any]:
    s = state.ensure_session()
    if req.package_zip and req.package_zip.strip():
        s = state.start_session(package_zip=req.package_zip, providers=None, validate_manifest=True)
    s.reset()
    csv_path = _resolve_data_csv(req.data_csv)
    online.start(
        session=s,
        data_csv=csv_path,
        start_utc=req.start_utc.strip() if isinstance(req.start_utc, str) and req.start_utc.strip() else None,
        end_utc=req.end_utc.strip() if isinstance(req.end_utc, str) and req.end_utc.strip() else None,
        speed=float(req.speed),
        max_rows=int(req.max_rows),
    )
    return {
        "message": "online replay started",
        "data_csv": str(csv_path),
        "speed": float(req.speed),
        "max_rows": int(req.max_rows),
    }


@app.post("/api/online/stop")
def api_online_stop() -> dict[str, Any]:
    online.stop()
    return {"message": "online replay stop signal sent"}


@app.get("/api/online/status")
def api_online_status() -> dict[str, Any]:
    s = state.ensure_session()
    return online.status(s)
