#!/usr/bin/env python3
"""Build b3r with the b3 grader and the PUBLIC test secret. No uploads."""

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.protocol import GENESIS
from sealedbench.v2.manifest_doc import build_b3_manifest, dumps_manifest
from sealedbench.v2.reference_set import build_reference
from sealedbench.v2.spec import CHAIN_HASH, TEST_SECRET
from sealedbench.v2.tarball import build_v2_tarball


def fake(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(b"REHEARSAL ONLY\0" + data).digest()).decode().rstrip("=")


def main() -> None:
    if ROOT.name != "sealedbench-b3r" or os.environ.get("SEALEDBENCH_DRY_UPLOAD") != "1":
        raise SystemExit("requires the b3r worktree and dry-upload mode")
    dest = ROOT / "results/batches/b3r"
    dest.mkdir(parents=True, exist_ok=True)
    gateway = dest / "gateway"
    gateway.mkdir(exist_ok=True)
    plain = build_v2_tarball(ROOT, TEST_SECRET, extra_files=["sealedbench/v2/grade_b3.py"])
    round_num = 33000000
    cmd = [os.environ["TLE"], "-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", str(round_num), "-a", "-f"]
    proc = subprocess.run(cmd, input=plain, capture_output=True, check=True, timeout=180)
    armor = proc.stdout
    reference = build_reference(ROOT, n=2)
    ref = reference["file_bytes"]
    tx = {"batch_id": "b3r", "dry_run": True, "items": {}}
    for kind, blob in (("generator-ciphertext", armor), ("reference", ref)):
        digest = hashlib.sha256(blob).hexdigest()
        txid = fake(blob)
        tx["items"][kind] = {"txid": txid, "sha256": digest, "bytes": len(blob), "dry_run": True}
        (gateway / txid).write_bytes(blob)
    unlock = GENESIS + (round_num - 1) * 3
    manifest = build_b3_manifest(
        ROOT,
        batch_id="b3r",
        release_round=round_num,
        unlock_unix=unlock,
        unlock_utc=datetime.fromtimestamp(unlock, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ciphertext_txid=tx["items"]["generator-ciphertext"]["txid"],
        ciphertext_sha256=tx["items"]["generator-ciphertext"]["sha256"],
        ciphertext_bytes=len(armor),
        plaintext_sha256=hashlib.sha256(plain).hexdigest(),
        plaintext_bytes=len(plain),
        reference_txid=tx["items"]["reference"]["txid"],
        reference_sha256=tx["items"]["reference"]["sha256"],
        reference_bytes=len(ref),
        vectors=[],
    )
    for family in manifest["generator"]["families"]:
        family["n"] = 2
    manifest["reference"].update(n=2, indexes="0..1")
    manifest["counts_note"] = "REHEARSAL ONLY: 2 per family plus 2 reference, 4 models"
    data = dumps_manifest(manifest)
    (dest / "manifest.json").write_bytes(data)
    manifest_txid = fake(data)
    tx["items"]["manifest"] = {
        "txid": manifest_txid,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "dry_run": True,
    }
    (gateway / manifest_txid).write_bytes(data)
    (dest / "txids.json").write_text(json.dumps(tx, indent=2) + "\n")
    (dest / "reference.json").write_bytes(ref)
    (dest / "generator.tlock").write_bytes(armor)
    print(f"REHEARSAL_SEALED round={round_num} bytes={len(armor)} models={len(manifest['models'])}")


if __name__ == "__main__":
    main()
