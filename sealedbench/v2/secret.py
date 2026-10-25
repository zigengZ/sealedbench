"""Load the 32-byte secret that ships inside the sealed tarball."""

from __future__ import annotations

from pathlib import Path

SECRET_NAME = "batch_secret.bin"


def secret_path() -> Path:
    return Path(__file__).resolve().parent / SECRET_NAME


def load_secret() -> bytes:
    path = secret_path()
    data = path.read_bytes()
    if len(data) != 32:
        raise RuntimeError(f"{SECRET_NAME} must be 32 bytes, got {len(data)}")
    return data
