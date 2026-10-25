"""Upload scores and the final index for a batch. Completions upload only if ≤ 100 KiB."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sealedbench.infer import batch_dir

ROOT = Path("/root/codes/sealedbench")
LIMIT = 100 * 1024


def _write_spec(items: list[dict]) -> Path:
    path = ROOT / "results" / "batches" / "upload_spec.json"
    path.write_text(json.dumps({"items": items}, indent=2) + "\n")
    return path


def _upload(items: list[dict]) -> None:
    if not items:
        return
    spec = _write_spec(items)
    proc = subprocess.run(["node", str(ROOT / "tools" / "upload_artifact.mjs"), str(spec)], cwd=ROOT, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"upload exit {proc.returncode}")


def publish_batch(batch: str) -> int:
    directory = batch_dir(batch)
    manifest = json.loads((directory / "manifest.json").read_text())
    scores_path = directory / "scores.json"
    scores = json.loads(scores_path.read_text())
    txids = json.loads((directory / "txids.json").read_text())
    completions = directory / "completions.tar.gz"
    comp_bytes = completions.read_bytes()
    upload_comp = len(comp_bytes) <= LIMIT
    items = [
        {
            "path": str(scores_path.relative_to(ROOT)),
            "type": "results",
            "batch": batch,
            "round": manifest["release_round"],
            "content_type": "application/json",
        }
    ]
    if upload_comp:
        items.append(
            {
                "path": str(completions.relative_to(ROOT)),
                "type": "completions",
                "batch": batch,
                "round": manifest["release_round"],
                "content_type": "application/gzip",
            }
        )
    _upload(items)
    txids = json.loads((directory / "txids.json").read_text())
    comp_record = {
        "uploaded": upload_comp,
        "sha256": scores["completions_sha256"],
        "bytes": scores["completions_bytes"],
        "repo_path": scores["completions_repo_path"],
    }
    if upload_comp:
        comp_record["txid"] = txids["items"]["completions"]["txid"]
    index = {
        "protocol_version": manifest["protocol_version"],
        "batch_id": batch,
        "batch_valid": scores["batch_valid"],
        "manifest_txid": txids["items"]["manifest"]["txid"],
        "manifest_sha256": txids["items"]["manifest"]["sha256"],
        "ciphertext_txid": txids["items"]["generator-ciphertext"]["txid"],
        "ciphertext_sha256": txids["items"]["generator-ciphertext"]["sha256"],
        "release_round": manifest["release_round"],
        "unlock_utc": manifest["unlock_utc"],
        "question_set_sha256": scores["question_set_sha256"],
        "results_txid": txids["items"]["results"]["txid"],
        "results_sha256": txids["items"]["results"]["sha256"],
        "completions": comp_record,
    }
    index_path = directory / "index.json"
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    _upload(
        [
            {
                "path": str(index_path.relative_to(ROOT)),
                "type": "index",
                "batch": batch,
                "round": manifest["release_round"],
                "content_type": "application/json",
            }
        ]
    )
    txids = json.loads((directory / "txids.json").read_text())
    print(f"PUBLISH index={txids['items']['index']['txid']} results={index['results_txid']} completions_uploaded={upload_comp}")
    return 0
