#!/usr/bin/env python3
"""Upload ciphertext, then the reference subset, then the manifests.

Stops if /root/sbw/p2r/HOLD exists.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.constants import BATCHES  # noqa: E402
from sealedbench.v2.manifest_doc import build_manifest, dumps_manifest  # noqa: E402
from sealedbench.v2.spec import CHAIN_HASH  # noqa: E402

HOLD = Path("/root/sbw/p2r/HOLD")


def txids(batch: str) -> dict:
    path = ROOT / "results" / "batches" / batch / "txids.json"
    if not path.exists():
        return {"batch_id": batch, "items": {}}
    return json.loads(path.read_text())


def upload(items: list[dict]) -> None:
    if HOLD.exists():
        raise SystemExit("HOLD exists; not uploading")
    spec = ROOT / "results" / "batches" / "v2_upload_spec.json"
    spec.write_text(json.dumps({"items": items}, indent=2) + "\n")
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "v2_upload.mjs"), str(spec)],
        cwd=str(ROOT),
        check=False,
    )
    if proc.returncode != 0:
        raise SystemExit(f"upload exit {proc.returncode}")


def item(path: str, type_: str, batch: str, content_type: str) -> dict:
    spec = BATCHES[batch]
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


def main() -> None:
    if HOLD.exists():
        raise SystemExit("HOLD exists; not uploading")
    prepare = json.loads((ROOT / "results" / "batches" / "b2" / "prepare.json").read_text())
    vectors = json.loads((ROOT / "sealedbench" / "v2" / "vectors.json").read_text())
    upload(
        [
            item("results/batches/b2/generator.tlock", "generator-ciphertext", "b2", "text/plain"),
            item("results/batches/cap2/generator.tlock", "generator-ciphertext", "cap2", "text/plain"),
            item("results/batches/b2/reference.json", "reference", "b2", "application/json"),
        ]
    )
    b2 = txids("b2")
    cap2 = txids("cap2")
    ref = b2["items"]["reference"]
    for batch, own, other_name, other in (
        ("b2", b2, "cap2", cap2),
        ("cap2", cap2, "b2", b2),
    ):
        spec = BATCHES[batch]
        cipher = own["items"]["generator-ciphertext"]
        doc = build_manifest(
            ROOT,
            batch_id=batch,
            release_round=spec["release_round"],
            unlock_unix=spec["unlock_unix"],
            unlock_utc=spec["unlock_utc"],
            peer_id=other_name,
            peer_ciphertext_sha256=other["items"]["generator-ciphertext"]["sha256"],
            ciphertext_txid=cipher["txid"],
            ciphertext_sha256=cipher["sha256"],
            ciphertext_bytes=cipher["bytes"],
            plaintext_sha256=prepare["ciphertext"][batch]["plaintext_sha256"],
            plaintext_bytes=prepare["ciphertext"][batch]["plaintext_bytes"],
            reference_txid=ref["txid"],
            reference_sha256=ref["sha256"],
            reference_bytes=ref["bytes"],
            vectors=vectors,
        )
        path = ROOT / "results" / "batches" / batch / "manifest.json"
        path.write_bytes(dumps_manifest(doc))
        print(f"manifest {batch} bytes={path.stat().st_size}", flush=True)
        if path.stat().st_size > 100 * 1024:
            raise SystemExit("manifest over 100 KiB")
    upload(
        [
            item("results/batches/b2/manifest.json", "manifest", "b2", "application/json"),
            item("results/batches/cap2/manifest.json", "manifest", "cap2", "application/json"),
        ]
    )
    print("SEAL_UPLOAD_OK", flush=True)


if __name__ == "__main__":
    main()
