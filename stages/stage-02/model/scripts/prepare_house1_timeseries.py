import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nilm_stage2.config import load_config


@dataclass
class SeriesStats:
    name: str
    rows_scanned: int
    rows_in_range: int
    unique_seconds: int
    first_second: int | None
    last_second: int | None


def parse_labels(labels_path: Path) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for line in labels_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            continue
        channel_id, appliance = parts
        mapping[appliance.strip().lower()] = int(channel_id)
    return mapping


def read_first_last_timestamp(path: Path) -> tuple[float | None, float | None]:
    first: float | None = None
    last: float | None = None

    with path.open("rb") as f:
        first_line = f.readline().decode("utf-8", errors="ignore").strip()
        if first_line:
            first = float(first_line.split()[0])

        f.seek(0, 2)
        end = f.tell()
        if end == 0:
            return first, None

        block_size = 8192
        buffer = b""
        pos = end
        while pos > 0:
            read_size = min(block_size, pos)
            pos -= read_size
            f.seek(pos)
            buffer = f.read(read_size) + buffer
            lines = buffer.splitlines()
            for line in reversed(lines):
                text = line.decode("utf-8", errors="ignore").strip()
                if text:
                    last = float(text.split()[0])
                    return first, last
            if pos == 0:
                break

    return first, last


def aggregate_file_to_second(
    file_path: Path,
    start_s: int,
    end_s: int,
    value_col: int,
    chunksize: int,
) -> tuple[pd.Series, SeriesStats]:
    sums = defaultdict(float)
    counts = defaultdict(int)
    rows_scanned = 0
    rows_in_range = 0
    seen_after_start = False

    col_names = list(range(value_col + 1))
    for chunk in pd.read_csv(
        file_path,
        sep=r"\s+",
        header=None,
        usecols=[0, value_col],
        names=col_names,
        chunksize=chunksize,
        engine="python",
    ):
        rows_scanned += len(chunk)
        ts = chunk[0].astype(float)
        vals = chunk[value_col].astype(float)
        sec = np.rint(ts.to_numpy()).astype(np.int64)

        chunk_min = int(sec.min())
        chunk_max = int(sec.max())
        if chunk_max < start_s:
            continue
        if chunk_max >= start_s:
            seen_after_start = True
        if chunk_min > end_s and seen_after_start:
            break
        if chunk_min > end_s and not seen_after_start:
            break

        mask = (sec >= start_s) & (sec <= end_s)
        if not np.any(mask):
            continue

        sec_in = sec[mask]
        vals_in = vals.to_numpy()[mask]
        rows_in_range += int(mask.sum())

        local_sum = defaultdict(float)
        local_count = defaultdict(int)
        for s, v in zip(sec_in, vals_in):
            local_sum[int(s)] += float(v)
            local_count[int(s)] += 1
        for s, v in local_sum.items():
            sums[s] += v
            counts[s] += local_count[s]

    if not sums:
        series = pd.Series(dtype=np.float32)
        stats = SeriesStats(
            name=file_path.name,
            rows_scanned=rows_scanned,
            rows_in_range=rows_in_range,
            unique_seconds=0,
            first_second=None,
            last_second=None,
        )
        return series, stats

    seconds = np.array(sorted(sums.keys()), dtype=np.int64)
    data = np.array([sums[s] / counts[s] for s in seconds], dtype=np.float32)
    series = pd.Series(data=data, index=seconds)
    stats = SeriesStats(
        name=file_path.name,
        rows_scanned=rows_scanned,
        rows_in_range=rows_in_range,
        unique_seconds=int(len(seconds)),
        first_second=int(seconds[0]),
        last_second=int(seconds[-1]),
    )
    return series, stats


def resolve_time_window(
    mains_path: Path,
    appliance_paths: Iterable[Path],
    start_s_arg: int | None,
    duration_hours: int,
) -> tuple[int, int]:
    first_candidates = []
    last_candidates = []

    paths = [mains_path, *list(appliance_paths)]
    for p in paths:
        first, last = read_first_last_timestamp(p)
        if first is None or last is None:
            raise ValueError(f"Cannot read timestamps from: {p}")
        first_candidates.append(int(np.ceil(first)))
        last_candidates.append(int(np.floor(last)))

    overlap_start = max(first_candidates)
    overlap_end = min(last_candidates)
    if overlap_start >= overlap_end:
        raise ValueError("No overlapping time range across mains and appliance channels")

    start_s = start_s_arg if start_s_arg is not None else overlap_start
    if start_s < overlap_start:
        start_s = overlap_start
    if start_s > overlap_end:
        raise ValueError("start-epoch is outside overlap range")

    if duration_hours <= 0:
        end_s = overlap_end
    else:
        end_s = min(overlap_end, start_s + duration_hours * 3600 - 1)
    if end_s <= start_s:
        raise ValueError("Time window is too short after applying bounds")

    return start_s, end_s


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare 1s aligned timeseries for UK-DALE house_1 without mutating raw data."
    )
    parser.add_argument("--config", default="configs/default.json")
    parser.add_argument("--out-dir", default="data/processed/house_1_1s")
    parser.add_argument("--start-epoch", type=int, default=None, help="Optional start second (epoch)")
    parser.add_argument(
        "--duration-hours",
        type=int,
        default=168,
        help="Window duration in hours; <=0 means full overlap range",
    )
    parser.add_argument("--ffill-limit-seconds", type=int, default=6)
    parser.add_argument("--chunksize", type=int, default=1_000_000)
    args = parser.parse_args()

    cfg = load_config(args.config)
    dataset = cfg.dataset
    raw_root = Path(dataset.get("raw_root", "./data/raw/uk-dale")).resolve()
    house = dataset.get("house", "house_1")
    appliances = [str(x).strip().lower() for x in dataset.get("appliances", [])]
    if not appliances:
        raise ValueError("No appliances configured in dataset.appliances")

    house_dir = raw_root / house
    if not house_dir.exists():
        raise FileNotFoundError(f"House directory not found: {house_dir}")

    labels_path = house_dir / "labels.dat"
    if not labels_path.exists():
        raise FileNotFoundError(f"labels.dat not found: {labels_path}")
    labels_map = parse_labels(labels_path)

    mains_path = house_dir / "mains.dat"
    if not mains_path.exists():
        raise FileNotFoundError(f"mains.dat not found: {mains_path}")

    appliance_paths: dict[str, Path] = {}
    for app in appliances:
        if app not in labels_map:
            known = ", ".join(sorted(labels_map.keys()))
            raise ValueError(f"Appliance '{app}' not found in labels.dat. Known: {known}")
        channel_id = labels_map[app]
        channel_path = house_dir / f"channel_{channel_id}.dat"
        if not channel_path.exists():
            raise FileNotFoundError(f"Channel file missing for {app}: {channel_path}")
        appliance_paths[app] = channel_path

    start_s, end_s = resolve_time_window(
        mains_path=mains_path,
        appliance_paths=appliance_paths.values(),
        start_s_arg=args.start_epoch,
        duration_hours=args.duration_hours,
    )

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Raw root (read-only): {raw_root}")
    print(f"Output dir (new copy): {out_dir}")
    print(f"House: {house}")
    print(f"Appliances: {appliances}")
    print(f"Time window: [{start_s}, {end_s}] ({end_s - start_s + 1} seconds)")

    mains_series, mains_stats = aggregate_file_to_second(
        file_path=mains_path,
        start_s=start_s,
        end_s=end_s,
        value_col=1,
        chunksize=args.chunksize,
    )

    app_series: dict[str, pd.Series] = {}
    app_stats: dict[str, SeriesStats] = {}
    for app, path in appliance_paths.items():
        s, st = aggregate_file_to_second(
            file_path=path,
            start_s=start_s,
            end_s=end_s,
            value_col=1,
            chunksize=args.chunksize,
        )
        app_series[app] = s
        app_stats[app] = st

    full_index = pd.RangeIndex(start_s, end_s + 1)
    df = pd.DataFrame(index=full_index)
    df["mains_w"] = mains_series.reindex(full_index)
    for app in appliances:
        # Hold appliance value for at most 6 seconds so we stay close to raw 6s telemetry.
        df[f"{app}_w"] = app_series[app].reindex(full_index).ffill(limit=args.ffill_limit_seconds)

    df.index.name = "epoch_s"
    df["timestamp_utc"] = pd.to_datetime(df.index.to_numpy(), unit="s", utc=True)
    ordered_cols = ["timestamp_utc", "mains_w", *[f"{a}_w" for a in appliances]]
    df = df[ordered_cols]

    valid_mask = df["mains_w"].notna()
    for app in appliances:
        valid_mask &= df[f"{app}_w"].notna()
    df_valid = df.loc[valid_mask].copy()

    full_csv = out_dir / "timeseries_1s_full.csv"
    valid_csv = out_dir / "timeseries_1s_train_ready.csv"
    df.to_csv(full_csv, encoding="utf-8")
    df_valid.to_csv(valid_csv, encoding="utf-8")

    report = {
        "raw_root_read_only": str(raw_root),
        "output_dir": str(out_dir),
        "house": house,
        "appliances": appliances,
        "time_window": {
            "start_epoch": start_s,
            "end_epoch": end_s,
            "duration_seconds": end_s - start_s + 1,
            "start_utc": pd.to_datetime(start_s, unit="s", utc=True).isoformat(),
            "end_utc": pd.to_datetime(end_s, unit="s", utc=True).isoformat(),
        },
        "rows": {
            "full_1s": int(len(df)),
            "train_ready": int(len(df_valid)),
            "train_ready_ratio": float(len(df_valid) / len(df)) if len(df) > 0 else 0.0,
        },
        "missing_ratio": {
            "mains_w": float(df["mains_w"].isna().mean()),
            **{f"{a}_w": float(df[f"{a}_w"].isna().mean()) for a in appliances},
        },
        "series_stats": {
            "mains": mains_stats.__dict__,
            **{a: st.__dict__ for a, st in app_stats.items()},
        },
        "rules": {
            "mains_fill": "none",
            "appliance_fill": f"forward_fill_limit_{args.ffill_limit_seconds}s",
            "raw_data_mutation": "disabled_by_design",
        },
        "artifacts": {
            "full_csv": str(full_csv),
            "train_ready_csv": str(valid_csv),
        },
    }

    report_path = out_dir / "quality_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Export completed:")
    print(f"- full 1s table: {full_csv}")
    print(f"- train-ready table: {valid_csv}")
    print(f"- quality report: {report_path}")


if __name__ == "__main__":
    main()
