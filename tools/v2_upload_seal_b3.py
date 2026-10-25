#!/usr/bin/env python3
"""Upload b3 ciphertext, then its reference, then its manifest.

cap3, when its ciphertext is already sealed, is uploaded after b3's manifest:
ciphertext then manifest. It reuses b3's reference txid.
Stops if /root/sbw/p2r/HOLD exists.
The phase ledger must stay within 20 uploads and 1.8 MiB.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.constants import B3_BATCHES
from sealedbench.v2.manifest_doc import build_b3_manifest, dumps_manifest
from sealedbench.v2.spec import CHAIN_HASH

HOLD = Path("/root/sbw/p2r/HOLD")
LEDGER = ROOT / "results/batches/p2r_upload_ledger.json"
MAX_COUNT = 20
MAX_TOTAL = int(1.8 * 1024 * 1024)


def txids(batch: str) -> dict:
    path = ROOT / "results/batches" / batch / "txids.json"
    if not path.exists():
        return {"batch_id": batch, "items": {}}
    return json.loads(path.read_text())


def item(path: str, type_: str, batch: str, content_type: str) -> dict:
    spec = B3_BATCHES[batch]
    return {
        "path": path,
        "type": type_,
        "batch": batch,
        "round": spec["release_round"],
        "unlock_unix": spec["unlock_unix"],
        "unlock_utc": spec["unlock_utc"],
        "content_type": content_type,
        "chain": CHAIN_HASH,
    }


def preflight(paths: list[str]) -> None:
    ledger = json.loads(LEDGER.read_text())
    pending = 0
    size = 0
    for rel in paths:
        data = (ROOT / rel).read_bytes()
        if len(data) > 100 * 1024:
            raise SystemExit(f"{rel} exceeds 100 KiB")
        batch = "cap3" if "/cap3/" in rel else "b3"
        kind = "manifest" if rel.endswith("manifest.json") else "reference" if rel.endswith("reference.json") else "generator-ciphertext"
        have = txids(batch)["items"].get(kind, {})
        import hashlib
        digest = hashlib.sha256(data).hexdigest()
        if have.get("txid") and have.get("sha256") == digest:
            continue
        pending += 1
        size += len(data)
    if ledger["count"] + pending > MAX_COUNT or ledger["total_bytes"] + size > MAX_TOTAL:
        raise SystemExit(f"budget count={ledger['count']} bytes={ledger['total_bytes']} pending={pending} size={size}")


def upload(items: list[dict]) -> None:
    if HOLD.exists():
        raise SystemExit("HOLD exists; not uploading")
    preflight([row["path"] for row in items])
    spec = ROOT / "results/batches/v2_upload_spec.json"
    spec.write_text(json.dumps({"items": items}, indent=2) + "\n")
    proc = subprocess.run(
        ["node", str(ROOT / "tools/v2_upload.mjs"), str(spec)],
        cwd=str(ROOT),
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"upload exit {proc.returncode}")


def write_manifest(batch: str, role: str, reference: dict, peer_sha: str | None) -> None:
    prepare = json.loads((ROOT / "results/batches/b3/prepare.json").read_text())
    vectors = json.loads((ROOT / "sealedbench/v2/vectors.json").read_text())
    own = txids(batch)
    spec = B3_BATCHES[batch]
    cipher = own["items"]["generator-ciphertext"]
    plain = prepare["ciphertext"][batch]
    doc = build_b3_manifest(
        ROOT,
        batch_id=batch,
        release_round=spec["release_round"],
        unlock_unix=spec["unlock_unix"],
        unlock_utc=spec["unlock_utc"],
        ciphertext_txid=cipher["txid"],
        ciphertext_sha256=cipher["sha256"],
        ciphertext_bytes=cipher["bytes"],
        plaintext_sha256=plain["plaintext_sha256"],
        plaintext_bytes=plain["plaintext_bytes"],
        reference_txid=reference["txid"],
        reference_sha256=reference["sha256"],
        reference_bytes=reference["bytes"],
        vectors=vectors,
        role=role,
        peer_ciphertext_sha256=peer_sha,
    )
    path = ROOT / "results/batches" / batch / "manifest.json"
    path.write_bytes(dumps_manifest(doc))
    if path.stat().st_size > 100 * 1024:
        raise SystemExit("manifest over 100 KiB")
    print(f"manifest {batch} bytes={path.stat().st_size}", flush=True)


def main() -> None:
    if HOLD.exists():
        raise SystemExit("HOLD exists; not uploading")
    upload(
        [
            item("results/batches/b3/generator.tlock", "generator-ciphertext", "b3", "text/plain"),
            item("results/batches/b3/reference.json", "reference", "b3", "application/json"),
        ]
    )
    b3 = txids("b3")
    reference = b3["items"]["reference"]
    write_manifest("b3", "b3", reference, None)
    upload([item("results/batches/b3/manifest.json", "manifest", "b3", "application/json")])
    cap3_cipher = ROOT / "results/batches/cap3/generator.tlock"
    if "--cap3" in sys.argv and cap3_cipher.is_file():
        upload([item("results/batches/cap3/generator.tlock", "generator-ciphertext", "cap3", "text/plain")])
        peer_sha = txids("b3")["items"]["generator-ciphertext"]["sha256"]
        write_manifest("cap3", "cap3", reference, peer_sha)
        upload([item("results/batches/cap3/manifest.json", "manifest", "cap3", "application/json")])
    print("SEAL_UPLOAD_B3_OK", flush=True)


if __name__ == "__main__":
    main()
