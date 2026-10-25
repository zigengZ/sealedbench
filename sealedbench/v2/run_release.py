"""Release a v2 batch after its round: decrypt, check the beacon, write items."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from sealedbench.infer import batch_dir, load_manifest
from sealedbench.items import loads_jsonl, question_set_sha256
from sealedbench.net import Fetcher
from sealedbench.paths import repo_root
from sealedbench.release import fetch_agreed_beacon, fetch_matching, safe_extract, tle_decrypt
from sealedbench.v2.spec import CHAIN_HASH
from sealedbench.v2.transport import gateways, retry


def _bls(beacon: dict) -> bool:
    proc = subprocess.run(
        ["node", str(repo_root() / "tools" / "verify_beacon.mjs")],
        input=json.dumps({"beacon": beacon, "round": beacon["round"]}).encode(),
        capture_output=True,
        check=False,
        cwd=str(repo_root()),
        timeout=120,
    )
    return proc.returncode == 0


def _generate(src: Path, chain: str, round_num: int, signature: bytes, counts: dict) -> bytes:
    script = (
        "import json, sys\n"
        "from sealedbench.v2.secret import load_secret\n"
        "from sealedbench.v2.spec import derive_seed\n"
        "from sealedbench.v2.generate import generate_batch\n"
        "from sealedbench.items import dumps_jsonl\n"
        "seed = derive_seed(sys.argv[1], int(sys.argv[2]), bytes.fromhex(sys.argv[3]), load_secret())\n"
        "items = generate_batch(seed, json.loads(sys.argv[4]))\n"
        "sys.stdout.buffer.write(dumps_jsonl(items))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", script, chain, str(round_num), signature.hex(), json.dumps(counts)],
        cwd=str(src),
        env=env,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode()[-1500:])
    return proc.stdout


def release_batch(batch: str) -> int:
    directory = batch_dir(batch)
    manifest = load_manifest(batch)
    txids = json.loads((directory / "txids.json").read_text())
    fetcher = Fetcher()
    cipher_id = manifest["ciphertext"]["txid"]
    if cipher_id != txids["items"]["generator-ciphertext"]["txid"]:
        print("RELEASE_FAIL manifest ciphertext txid disagrees with txids.json")
        return 2
    got = retry("ciphertext", lambda: fetch_matching(cipher_id, manifest["ciphertext"]["sha256"], fetcher, gateways=gateways()))
    armor = got["body"]
    beacon, meta = retry("beacon", lambda: fetch_agreed_beacon(manifest["release_round"], fetcher))
    if not _bls(beacon):
        print("RELEASE_FAIL BLS signature check")
        return 2
    def decrypt():
        code, plain, err = tle_decrypt(armor)
        if code:
            raise RuntimeError(f"tle {code} {err[-300:]}")
        return code, plain, err

    code, plain, err = retry("decrypt", decrypt)
    if code != 0:
        print(f"RELEASE_FAIL tle {code} {err[-300:]}")
        return 2
    if __import__("hashlib").sha256(plain).hexdigest() != manifest["plaintext_tarball_sha256"]:
        print("RELEASE_FAIL plaintext hash")
        return 2
    work = repo_root() / "results" / "batches" / batch / "src"
    if work.exists():
        import shutil

        shutil.rmtree(work)
    safe_extract(plain, work)
    counts = {row["name"]: int(row["n"]) for row in manifest["generator"]["families"]}
    signature = bytes.fromhex(beacon["signature"])
    jsonl = _generate(work, manifest["drand"]["chain_hash"], manifest["release_round"], signature, counts)
    items = loads_jsonl(jsonl)
    qhash = question_set_sha256(items)
    (directory / "items.jsonl").write_bytes(jsonl)
    (directory / "beacon.json").write_text(json.dumps(beacon, indent=2, sort_keys=True) + "\n")
    record = {
        "batch_id": batch,
        "batch_valid": None,
        "question_set_sha256": qhash,
        "n_items": len(items),
        "bls_verified": True,
        "beacon_relays_ok": meta.get("relays_ok"),
        "seed_input": "BLS signature bytes plus the sealed 32-byte secret",
        "chain_hash": CHAIN_HASH,
    }
    (directory / "release.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"RELEASE_OK items={len(items)} qsha={qhash}")
    return 0
