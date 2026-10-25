"""Deterministic v2 generator tarball.

The sealed tree contains the v2 generator, the v1 arith and graph samplers
it calls, and batch_secret.bin. It does not contain the v1 code_output
module, whose oracle uses a wall-clock timeout.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from sealedbench.v2.generate import template_bank
from sealedbench.v2.spec import canon

REPO_FILES = [
    "sealedbench/__init__.py",
    "sealedbench/items.py",
    "sealedbench/rng.py",
    "sealedbench/families/arith_word.py",
    "sealedbench/families/graph_path.py",
    "sealedbench/v2/__init__.py",
    "sealedbench/v2/spec.py",
    "sealedbench/v2/prng.py",
    "sealedbench/v2/secret.py",
    "sealedbench/v2/generate.py",
    "sealedbench/v2/grade.py",
    "sealedbench/v2/diversity.py",
    "sealedbench/v2/families/__init__.py",
    "sealedbench/v2/families/code_output.py",
]

FAMILIES_INIT = (
    '"""v2 sealed tree. Import arith_word and graph_path directly.\n'
    "\n"
    "This package init does not import the v1 code_output sampler.\n"
    '"""\n'
).encode("utf-8")

GRADER_FILES = [
    "sealedbench/v2/grade.py",
]


def grader_sha256(root: Path, files: list[str] | None = None) -> str:
    digest = hashlib.sha256()
    chosen = list(GRADER_FILES if files is None else files)
    for rel in sorted(chosen):
        data = (root / rel).read_bytes()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
    return digest.hexdigest()


def build_v2_tarball(root: Path, secret: bytes, extra_files: list[str] | None = None) -> bytes:
    if len(secret) != 32:
        raise ValueError("secret must be 32 bytes")
    rels = list(REPO_FILES)
    for rel in extra_files or []:
        if rel not in rels:
            rels.append(rel)
    files: list[tuple[str, bytes]] = []
    for rel in rels:
        files.append((rel, (root / rel).read_bytes()))
    files.append(("sealedbench/families/__init__.py", FAMILIES_INIT))
    bank = (canon(template_bank()) + "\n").encode("utf-8")
    files.append(("sealedbench/v2/template_bank.json", bank))
    files.append(("sealedbench/v2/batch_secret.bin", bytes(secret)))
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
    return gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def template_bank_bytes() -> bytes:
    return (canon(template_bank()) + "\n").encode("utf-8")
