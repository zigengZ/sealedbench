"""Deterministic generator tarball.

Sorted paths, ustar, mtime 0, uid/gid 0, mode 0644 for files and 0755 for
directories. gzip stores no filename and mtime 0, matching gzip -n.
Only the allow-listed generator sources are sealed. Verifier and manifest
code stay outside the hash.
"""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path

SEALED_PATHS = [
    "sealedbench/__init__.py",
    "sealedbench/seed.py",
    "sealedbench/rng.py",
    "sealedbench/extract.py",
    "sealedbench/grade.py",
    "sealedbench/items.py",
    "sealedbench/generate.py",
    "sealedbench/families/__init__.py",
    "sealedbench/families/arith_word.py",
    "sealedbench/families/code_output.py",
    "sealedbench/families/graph_path.py",
]


def build_generator_tarball(root: Path) -> bytes:
    files = []
    for rel in SEALED_PATHS:
        path = root / rel
        if not path.is_file():
            raise FileNotFoundError(rel)
        files.append((rel, path.read_bytes()))
    dirs = set()
    for rel, _data in files:
        parts = rel.split("/")
        for index in range(1, len(parts)):
            dirs.add("/".join(parts[:index]))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(dirs):
            info = tarfile.TarInfo(name=name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            tar.addfile(info)
        for name, data in sorted(files):
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.type = tarfile.REGTYPE
            tar.addfile(info, io.BytesIO(data))
    payload = raw.getvalue()
    return gzip.compress(payload, compresslevel=9, mtime=0)
