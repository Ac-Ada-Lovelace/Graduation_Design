from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
from torch import nn


@dataclass
class SplitData:
    mains: np.ndarray
    targets: np.ndarray


@dataclass
class Normalization:
    mains_mean: float
    mains_std: float
    target_mean: dict[str, float]
    target_std: dict[str, float]


class Seq2PointNet(nn.Module):
    """Seq2Point-style CNN for multi-appliance regression.

    `variant="avgpool"` keeps legacy behavior for backward compatibility.
    `variant="classic"` uses a flattened temporal head, which generally preserves
    event amplitude better than global average pooling.
    """

    def __init__(
        self,
        n_outputs: int,
        window_size: int = 601,
        variant: str = "avgpool",
    ) -> None:
        super().__init__()
        if window_size <= 0:
            raise ValueError("window_size must be > 0")
        if variant not in {"avgpool", "classic"}:
            raise ValueError("variant must be one of: avgpool, classic")

        self.variant = variant
        self.window_size = int(window_size)
        self.n_outputs = int(n_outputs)

        self.features = nn.Sequential(
            nn.Conv1d(1, 30, kernel_size=10, padding=4),
            nn.ReLU(),
            nn.Conv1d(30, 30, kernel_size=8, padding=3),
            nn.ReLU(),
            nn.Conv1d(30, 40, kernel_size=6, padding=2),
            nn.ReLU(),
            nn.Conv1d(40, 50, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(50, 50, kernel_size=5, padding=2),
            nn.ReLU(),
        )

        if self.variant == "avgpool":
            self.pool = nn.AdaptiveAvgPool1d(1)
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(50, 128),
                nn.ReLU(),
                nn.Linear(128, n_outputs),
            )
        else:
            self.pool = nn.Identity()
            flat_dim = self._infer_flat_dim(self.window_size)
            self.head = nn.Sequential(
                nn.Flatten(),
                nn.Linear(flat_dim, 1024),
                nn.ReLU(),
                nn.Linear(1024, 512),
                nn.ReLU(),
                nn.Linear(512, n_outputs),
            )

    def _infer_flat_dim(self, window_size: int) -> int:
        with torch.no_grad():
            x = torch.zeros(1, 1, window_size, dtype=torch.float32)
            y = self.features(x)
            return int(y.shape[1] * y.shape[2])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, window_size, 1] -> [B, 1, window_size]
        x = x.transpose(1, 2)
        x = self.features(x)
        x = self.pool(x)
        return self.head(x)


def infer_model_variant_from_state_dict(state_dict: dict[str, torch.Tensor]) -> str:
    # Legacy checkpoints include `features.10.*` from AdaptiveAvgPool1d plus
    # head first linear in_features=50. Classic has larger in_features.
    w = state_dict.get("head.1.weight")
    if w is None:
        return "avgpool"
    in_features = int(w.shape[1])
    if in_features > 50:
        return "classic"
    return "avgpool"


def load_train_ready_frame(csv_path: str | Path, appliances: Iterable[str]) -> pd.DataFrame:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Train-ready CSV not found: {path}")
    cols = ["mains_w", *[f"{a}_w" for a in appliances]]
    frame = pd.read_csv(path)
    missing = [c for c in cols if c not in frame.columns]
    if missing:
        raise ValueError(f"Required columns missing from {path}: {missing}")
    frame = frame[cols].dropna()
    if frame.empty:
        raise ValueError(f"No usable rows after dropna in: {path}")
    return frame


def split_by_time(
    frame: pd.DataFrame, appliances: list[str], train_ratio: float, val_ratio: float
) -> tuple[SplitData, SplitData, SplitData]:
    if train_ratio <= 0 or val_ratio <= 0 or (train_ratio + val_ratio) >= 1:
        raise ValueError("train_ratio and val_ratio must satisfy: >0 and train+val<1")

    n = len(frame)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    if train_end < 2 or (val_end - train_end) < 2 or (n - val_end) < 2:
        raise ValueError("Dataset too small after split; adjust ratios or provide more data")

    mains = frame["mains_w"].to_numpy(dtype=np.float32)
    targets = frame[[f"{a}_w" for a in appliances]].to_numpy(dtype=np.float32)

    train = SplitData(mains=mains[:train_end], targets=targets[:train_end])
    val = SplitData(mains=mains[train_end:val_end], targets=targets[train_end:val_end])
    test = SplitData(mains=mains[val_end:], targets=targets[val_end:])
    return train, val, test


def compute_normalization(train: SplitData, appliances: list[str]) -> Normalization:
    mains_mean = float(train.mains.mean())
    mains_std = float(train.mains.std())
    if mains_std < 1e-6:
        mains_std = 1.0

    t_mean = train.targets.mean(axis=0)
    t_std = train.targets.std(axis=0)
    t_std = np.where(t_std < 1e-6, 1.0, t_std)

    return Normalization(
        mains_mean=mains_mean,
        mains_std=float(mains_std),
        target_mean={a: float(t_mean[i]) for i, a in enumerate(appliances)},
        target_std={a: float(t_std[i]) for i, a in enumerate(appliances)},
    )


def build_windows(split: SplitData, window_size: int) -> tuple[np.ndarray, np.ndarray]:
    if window_size % 2 == 0:
        raise ValueError("window_size must be odd for center-point prediction")
    if len(split.mains) < window_size:
        return np.empty((0, window_size), dtype=np.float32), np.empty(
            (0, split.targets.shape[1]), dtype=np.float32
        )

    x = np.lib.stride_tricks.sliding_window_view(split.mains, window_size).astype(np.float32)
    center = window_size // 2
    y = split.targets[center : center + len(x)].astype(np.float32)
    return x, y


def normalize_windows(
    x: np.ndarray, y: np.ndarray, appliances: list[str], norm: Normalization
) -> tuple[np.ndarray, np.ndarray]:
    x_norm = (x - norm.mains_mean) / norm.mains_std
    x_norm = x_norm[..., np.newaxis].astype(np.float32)

    t_mean = np.array([norm.target_mean[a] for a in appliances], dtype=np.float32)
    t_std = np.array([norm.target_std[a] for a in appliances], dtype=np.float32)
    y_norm = ((y - t_mean) / t_std).astype(np.float32)
    return x_norm, y_norm


def denormalize_targets(y_norm: np.ndarray, appliances: list[str], norm: Normalization) -> np.ndarray:
    t_mean = np.array([norm.target_mean[a] for a in appliances], dtype=np.float32)
    t_std = np.array([norm.target_std[a] for a in appliances], dtype=np.float32)
    return (y_norm * t_std) + t_mean
