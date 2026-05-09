from __future__ import annotations

import os
from typing import Any

import requests


DEFAULT_STAGE02_BASE_URL = "http://127.0.0.1:18080"


class Stage02Client:
    def __init__(self, base_url: str | None = None, timeout_s: float = 5.0) -> None:
        self.base_url = (base_url or os.getenv("STAGE02_BASE_URL") or DEFAULT_STAGE02_BASE_URL).rstrip("/")
        self.timeout_s = timeout_s

    def get_json(self, path: str) -> dict[str, Any]:
        resp = requests.get(f"{self.base_url}{path}", timeout=self.timeout_s)
        resp.raise_for_status()
        raw = resp.json()
        return raw if isinstance(raw, dict) else {}

    def post_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = requests.post(f"{self.base_url}{path}", json=payload or {}, timeout=self.timeout_s)
        resp.raise_for_status()
        raw = resp.json()
        return raw if isinstance(raw, dict) else {}

    def health(self) -> dict[str, Any]:
        return self.get_json("/health")

    def meta(self) -> dict[str, Any]:
        return self.get_json("/api/meta")

    def online_status(self) -> dict[str, Any]:
        return self.get_json("/api/online/status")

    def latest(self) -> dict[str, Any]:
        return self.get_json("/session/latest")

