"""Release a batch: download the ciphertext, decrypt, derive the seed, write items.

The ciphertext is fetched from a gateway. Local tlock files are not the source.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from sealedbench.infer import batch_dir
from sealedbench.items import loads_jsonl, question_set_sha256
from sealedbench.net import Fetcher
from sealedbench.observe import before_unlock, observe_item
from sealedbench.protocol import CHAIN_HASH, DRAND_URL

ROOT = Path("/root/codes/sealedbench")
CACHE = Path("/root/.cache/sealedbench")
TLE = os.environ.get("TLE", "/root/.cache/sealedbench/gopath/bin/tle")
DATA_GATEWAYS = (
    "https://ar-io.dev",
    "https://arweave.net",
    "https://ario.zigza.xyz",
    "https://turbo-gateway.com",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_matching(txid: str, expected: str, fetcher: Fetcher, require_hosts: tuple[str, ...] = ("https://ar-io.dev", "https://arweave.net")) -> dict:
    """Download txid from gateways. One of ar-io.dev or arweave.net must match."""
    hits = []
    body = None
    for host in DATA_GATEWAYS:
        url = f"{host}/{txid}"
        status, _headers, raw = fetcher.get(url)
        digest = _sha256(raw) if raw else None
        hit = {"host": host, "http": status, "bytes": len(raw), "sha256": digest, "match": digest == expected and status == 200}
        hits.append(hit)
        if hit["match"] and body is None:
            body = raw
    required_ok = any(hit["match"] and hit["host"] in require_hosts for hit in hits)
    if body is None or not required_ok:
        raise RuntimeError(f"ciphertext/manifest not served with the expected sha256: {hits}")
    return {"body": body, "gateways": hits}


def fetch_beacon(round_num: int, fetcher: Fetcher) -> dict:
    url = f"{DRAND_URL}/public/{round_num}"
    status, _headers, body = fetcher.get(url)
    if status != 200:
        raise RuntimeError(f"beacon HTTP {status}")
    parsed = json.loads(body)
    if int(parsed.get("round", -1)) != int(round_num):
        raise RuntimeError(f"beacon round {parsed.get('round')} != {round_num}")
    if not parsed.get("randomness") or not parsed.get("signature"):
        raise RuntimeError("beacon missing randomness or signature")
    return parsed


def tle_decrypt(armor: bytes) -> tuple[int, bytes, str]:
    proc = subprocess.run(
        [TLE, "-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
        input=armor,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", errors="replace")


def js_decrypt(armor: bytes, dest: Path) -> tuple[int, bytes, str]:
    dest.mkdir(parents=True, exist_ok=True)
    src = dest / "armor.tlock"
    out = dest / "js-plain.bin"
    src.write_bytes(armor)
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "tlock_decrypt.mjs"), str(src), str(out)],
        capture_output=True,
        check=False,
        cwd=str(ROOT),
    )
    text = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    if proc.returncode == 0 and out.exists():
        return 0, out.read_bytes(), text
    return proc.returncode or 1, b"", text


def safe_extract(tarball: bytes, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    blob = dest.parent / "generator.tar.gz"
    blob.write_bytes(tarball)
    with tarfile.open(blob, "r:gz") as tar:
        root = dest.resolve()
        for member in tar.getmembers():
            name = member.name
            if name.startswith("/") or ".." in name.split("/"):
                raise RuntimeError(f"unsafe tar member {name}")
            target = (root / name).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"unsafe tar target {name}")
        tar.extractall(dest)


def regenerate(tarball: bytes, chain_hash: str, round_num: int, randomness: str, counts: dict) -> bytes:
    work = CACHE / "work" / f"gen-{round_num}"
    if work.exists():
        shutil.rmtree(work)
    src = work / "src"
    safe_extract(tarball, src)
    driver = (
        "import json, sys\n"
        "from sealedbench.seed import seed_bytes\n"
        "from sealedbench.generate import generate_batch\n"
        "from sealedbench.items import dumps_jsonl\n"
        "seed = seed_bytes(sys.argv[1], int(sys.argv[2]), sys.argv[3])\n"
        "items = generate_batch(seed, json.loads(sys.argv[4]))\n"
        "sys.stdout.buffer.write(dumps_jsonl(items))\n"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-c", driver, chain_hash, str(round_num), randomness, json.dumps(counts)],
        cwd=str(src),
        env=env,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", errors="replace")[-2000:]
        raise RuntimeError(f"generator exited {proc.returncode}: {tail}")
    return proc.stdout


def _counts(manifest: dict) -> dict:
    return {row["name"]: int(row["n"]) for row in manifest["generator"]["families"]}


def _load_txids(batch: str) -> dict:
    return json.loads((batch_dir(batch) / "txids.json").read_text())


def release_batch(batch: str) -> int:
    directory = batch_dir(batch)
    manifest = json.loads((directory / "manifest.json").read_text())
    txids = _load_txids(batch)
    fetcher = Fetcher()
    cipher_id = txids["items"]["generator-ciphertext"]["txid"]
    manifest_id = txids["items"]["manifest"]["txid"]
    expected_cipher = manifest["ciphertext"]["sha256"]
    print(f"RELEASE download {cipher_id}", flush=True)
    got = None
    download_deadline = time.time() + 30 * 60
    download_error = None
    while time.time() < download_deadline:
        try:
            got = fetch_matching(cipher_id, expected_cipher, fetcher)
            break
        except Exception as exc:
            download_error = str(exc)
            print(f"RELEASE download wait {download_error[:300]}", flush=True)
            time.sleep(30)
    if got is None:
        print(f"RELEASE_FAIL download {download_error}")
        return 2
    armor = got["body"]
    if _sha256(armor) != expected_cipher:
        raise RuntimeError("downloaded ciphertext hash mismatch")
    beacon = None
    last_error = None
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        try:
            beacon = fetch_beacon(manifest["release_round"], fetcher)
            break
        except Exception as exc:  # network or not-yet-published
            last_error = str(exc)
            print(f"RELEASE beacon wait {last_error}", flush=True)
            time.sleep(10)
    if beacon is None:
        print(f"RELEASE_FAIL beacon {last_error}")
        return 2
    (directory / "beacon.json").write_text(json.dumps(beacon, indent=2, sort_keys=True) + "\n")
    code, plain, err = 1, b"", ""
    for _attempt in range(12):
        code, plain, err = tle_decrypt(armor)
        if code == 0:
            break
        if "too early" in err.lower():
            print("RELEASE decrypt a few seconds early; retrying", flush=True)
            time.sleep(5)
            continue
        break
    js_code, js_plain, js_text = js_decrypt(armor, CACHE / "work" / "js-decrypt")
    if code != 0:
        print(f"RELEASE_FAIL tle {code} {err[-500:]}")
        return 2
    if _sha256(plain) != manifest["generator"]["generator_sha256"]:
        print("RELEASE_FAIL decrypted tarball hash mismatch")
        return 2
    js_match = js_code == 0 and js_plain == plain
    counts = _counts(manifest)
    jsonl = regenerate(
        plain,
        manifest["drand"]["chain_hash"],
        manifest["release_round"],
        beacon["randomness"],
        counts,
    )
    items = loads_jsonl(jsonl)
    qhash = question_set_sha256(items)
    (directory / "items.jsonl").write_bytes(jsonl)
    print("RELEASE observe inclusion", flush=True)
    manifest_obs = observe_item(manifest_id, _sha256((directory / "manifest.json").read_bytes()), fetcher)
    cipher_obs = observe_item(cipher_id, expected_cipher, fetcher)
    (directory / "inclusion_manifest.json").write_text(json.dumps(manifest_obs, indent=2, sort_keys=True) + "\n")
    (directory / "inclusion_ciphertext.json").write_text(json.dumps(cipher_obs, indent=2, sort_keys=True) + "\n")
    m_flag = before_unlock(manifest_obs, manifest["unlock_unix"])
    c_flag = before_unlock(cipher_obs, manifest["unlock_unix"])
    valid = m_flag == "PASS" and c_flag == "PASS"
    if valid:
        note = (
            f"Manifest bundle L1 timestamp {manifest_obs['block']['timestamp_utc']} and "
            f"ciphertext bundle L1 timestamp {cipher_obs['block']['timestamp_utc']} are before "
            f"{manifest['unlock_utc']}. L1 status source manifest={manifest_obs['l1']['source']} "
            f"ciphertext={cipher_obs['l1']['source']}."
        )
    else:
        note = (
            f"Inclusion before unlock is manifest={m_flag} ciphertext={c_flag}. "
            "The batch is INVALID under the reporting policy and is still scored."
        )
    record = {
        "batch_id": batch,
        "batch_valid": valid,
        "validity_note": note,
        "manifest_inclusion": m_flag,
        "ciphertext_inclusion": c_flag,
        "question_set_sha256": qhash,
        "n_items": len(items),
        "generator_sha256": _sha256(plain),
        "ciphertext_sha256": _sha256(armor),
        "beacon_round": beacon["round"],
        "randomness_sha256": _sha256(beacon["randomness"].encode("ascii")),
        "decrypt_tool": "tle -d (Go tlock v1.2.0) verified the beacon signature by decrypting",
        "js_decrypt_match": js_match,
        "js_decrypt_note": js_text[-400:],
        "download_gateways": got["gateways"],
        "payload_in_bundle_manifest": (manifest_obs.get("payload") or {}).get("ok"),
        "payload_in_bundle_ciphertext": (cipher_obs.get("payload") or {}).get("ok"),
    }
    (directory / "release.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"RELEASE_OK items={len(items)} qsha={qhash} valid={valid} js_match={js_match}")
    return 0
