#!/usr/bin/env python3
"""Seal b3 locally, and cap3 when requested. Does not upload.

Secrets stay in /root/sbw/p2r/secrets (mode 0600) and inside the ciphertext.
This script never prints secret bytes.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.constants import B2_CIPHERTEXT_SHA256, B3_BATCHES, CAP2_CIPHERTEXT_SHA256
from sealedbench.v2.reference_set import build_reference
from sealedbench.v2.spec import CHAIN_HASH
from sealedbench.v2.tarball import build_v2_tarball, sha256

SECRETS = Path("/root/sbw/p2r/secrets")
TLE = os.environ.get("TLE", "/root/.cache/sealedbench/gopath/bin/tle")
GENERATOR_FILES = [
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


def load_secret(batch: str) -> bytes:
    SECRETS.mkdir(parents=True, exist_ok=True)
    path = SECRETS / f"{batch}.bin"
    if path.exists():
        data = path.read_bytes()
        if len(data) != 32:
            raise SystemExit(f"{batch} secret is not 32 bytes")
        return data
    data = os.urandom(32)
    path.write_bytes(data)
    path.chmod(0o600)
    return data


def encrypt(plain: bytes, round_num: int) -> bytes:
    proc = subprocess.run(
        [TLE, "-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", str(round_num), "-a"],
        input=plain,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or len(proc.stdout) < 80:
        err = proc.stderr.decode("utf-8", errors="replace")[-300:]
        raise SystemExit(f"encrypt failed rc={proc.returncode} {err}")
    return proc.stdout


def early_decrypt(batch: str, armor: bytes, path: Path) -> dict:
    go = subprocess.run(
        [TLE, "-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
        input=armor,
        capture_output=True,
        check=False,
    )
    js = subprocess.run(
        ["node", str(ROOT / "tools" / "v2_early_decrypt.mjs"), str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    if go.returncode == 0 or js.returncode != 0:
        raise SystemExit(f"early decrypt did not refuse {batch} go={go.returncode} js={js.returncode}")
    return {
        "go_exit": go.returncode,
        "go_stderr": go.stderr.decode("utf-8", errors="replace")[-300:],
        "js": (js.stdout + js.stderr)[-400:].strip(),
    }


def assert_declared_hashes() -> None:
    for batch, expected in (("b2", B2_CIPHERTEXT_SHA256), ("cap2", CAP2_CIPHERTEXT_SHA256)):
        manifest = json.loads((ROOT / "results/batches" / batch / "manifest.json").read_text())
        if manifest["ciphertext"]["sha256"] != expected:
            raise SystemExit(f"{batch} ciphertext hash does not match the declared constant")


def generator_matches_seal() -> bool:
    proc = subprocess.run(
        ["git", "diff", "--quiet", "e6b8795", "--", *GENERATOR_FILES],
        cwd=str(ROOT),
        check=False,
    )
    return proc.returncode == 0


def seal_one(batch: str, secret: bytes) -> dict:
    spec = B3_BATCHES[batch]
    plain = build_v2_tarball(ROOT, secret, extra_files=["sealedbench/v2/grade_b3.py"])
    if len(plain) > 100 * 1024:
        raise SystemExit(f"{batch} tarball {len(plain)} exceeds 100 KiB")
    armor = encrypt(plain, spec["release_round"])
    dest = ROOT / "results/batches" / batch
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / "generator.tlock"
    path.write_bytes(armor)
    early = early_decrypt(batch, armor, path)
    record = {
        "sha256": sha256(armor),
        "bytes": len(armor),
        "plaintext_sha256": sha256(plain),
        "plaintext_bytes": len(plain),
        "early_decrypt": early,
    }
    print(f"sealed {batch} cipher={record['sha256']} bytes={record['bytes']} early_go={early['go_exit']}", flush=True)
    return record


def main() -> None:
    if Path("/root/sbw/p2r/HOLD").exists():
        raise SystemExit("HOLD exists")
    assert_declared_hashes()
    batches = ["b3"]
    if "--cap3" in sys.argv:
        batches.append("cap3")
    secrets = {batch: load_secret(batch) for batch in batches}
    digests = []
    for name in ("b2", "cap2", *batches):
        path = SECRETS / f"{name}.bin"
        if path.exists():
            digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
    if len(digests) != len(set(digests)):
        raise SystemExit("batch secrets must differ")
    if not generator_matches_seal():
        raise SystemExit("generator files differ from the b2 seal commit")
    diversity = json.loads((ROOT / "results/batches/b2/diversity.json").read_text())
    if not diversity.get("gate_pass"):
        raise SystemExit("b2 diversity gate was not a pass")
    cipher = {batch: seal_one(batch, secrets[batch]) for batch in batches}
    reference = build_reference(ROOT)
    ref_path = ROOT / "results/batches/b3/reference.json"
    ref_path.write_bytes(reference["file_bytes"])
    if hashlib.sha256(ref_path.read_bytes()).hexdigest() != reference["file_sha256"]:
        raise SystemExit("reference bytes drifted")
    if len(reference["file_bytes"]) > 100 * 1024:
        raise SystemExit("reference over 100 KiB")
    print(f"reference bytes={len(reference['file_bytes'])} sha256={reference['file_sha256']}", flush=True)
    record = {
        "ciphertext": {batch: {key: value for key, value in row.items() if key != "early_decrypt"} for batch, row in cipher.items()},
        "early_decrypt": {batch: row["early_decrypt"] for batch, row in cipher.items()},
        "reference_sha256": reference["file_sha256"],
        "reference_bytes": len(reference["file_bytes"]),
        "generator_matches_b2_seal_commit": True,
        "diversity_gate_pass_from_b2": True,
        "diversity_not_rerun": "generator bytes match e6b8795; b2 gate already passed",
        "n_predict": "768/512",
    }
    (ROOT / "results/batches/b3/prepare.json").write_text(json.dumps(record, indent=2) + "\n")
    print("PREPARE_B3_OK", flush=True)


if __name__ == "__main__":
    main()
