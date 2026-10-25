"""Repo and cache locations. No hardcoded /root path is required."""

from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env = os.environ.get("SEALEDBENCH_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[1]


def cache_root() -> Path:
    env = os.environ.get("SEALEDBENCH_CACHE")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "sealedbench"
