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

from sealedbench.paths import cache_root, repo_root

ROOT = repo_root()
CACHE = cache_root()
TLE = os.environ.get("TLE", str(CACHE / "gopath" / "bin" / "tle"))
DATA_GATEWAYS = (
    "https://ar-io.dev",
    "https://arweave.net",
    "https://turbo-gateway.com",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class FetchError(RuntimeError):
    """A download failed. kind is 'mismatch' or 'unavailable'."""

    def __init__(self, message: str, hits: list, kind: str):
        super().__init__(message)
        self.hits = hits
        self.kind = kind


def download_deadline(now: float, unlock_unix: int) -> float:
    """Retry until two hours after unlock, and at least two hours from now."""
    return max(float(now) + 2 * 60 * 60, float(unlock_unix) + 2 * 60 * 60)


def beacon_binding_error(beacon: dict) -> str | None:
    """randomness must be SHA-256 of the signature bytes. This does not change the seed."""
    randomness = str(beacon.get("randomness") or "").strip().lower()
    signature = str(beacon.get("signature") or "").strip().lower()
    if not randomness or not signature:
        return "beacon missing randomness or signature"
    try:
        sig_bytes = bytes.fromhex(signature)
    except ValueError:
        return "signature is not hex"
    if not sig_bytes:
        return "signature is empty"
    digest = hashlib.sha256(sig_bytes).hexdigest()
    if digest != randomness:
        return f"randomness {randomness} != sha256(signature) {digest}"
    return None


def fetch_matching(txid: str, expected: str, fetcher: Fetcher, require_hosts: tuple[str, ...] | None = None, *, gateways: tuple[str, ...] | None = None) -> dict:
    """Download txid. Any gateway whose sha256 matches is enough.

    require_hosts is accepted and ignored so existing callers keep working.
    The bytes are self-authenticating. HTTP 404, 429, and connection errors
    are unavailable, not a hash mismatch.
    """
    del require_hosts
    hits = []
    body = None
    mismatch = False
    for host in (DATA_GATEWAYS if gateways is None else gateways):
        url = f"{host}/{txid}"
        try:
            status, _headers, raw = fetcher.get(url)
        except Exception as exc:
            hits.append(
                {
                    "host": host,
                    "http": 0,
                    "bytes": 0,
                    "sha256": None,
                    "match": False,
                    "error": str(exc)[:200],
                }
            )
            continue
        digest = _sha256(raw) if raw else None
        match = bool(status == 200 and raw and digest == expected)
        if status == 200 and raw and digest != expected:
            mismatch = True
        hits.append({"host": host, "http": status, "bytes": len(raw), "sha256": digest, "match": match})
        if match and body is None:
            body = raw
    if body is not None:
        return {"body": body, "gateways": hits}
    kind = "mismatch" if mismatch else "unavailable"
    raise FetchError(f"ciphertext/manifest not served with the expected sha256: {hits}", hits, kind)


def fetch_beacon(round_num: int, fetcher: Fetcher, base_url: str | None = None) -> dict:
    base = (base_url or DRAND_URL).rstrip("/")
    url = f"{base}/public/{round_num}"
    status, _headers, body = fetcher.get(url)
    if status != 200 or not body:
        raise RuntimeError(f"beacon HTTP {status} from {base}")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"beacon JSON from {base}: {exc}") from exc
    if int(parsed.get("round", -1)) != int(round_num):
        raise RuntimeError(f"beacon round {parsed.get('round')} != {round_num}")
    binding = beacon_binding_error(parsed)
    if binding:
        raise RuntimeError(binding)
    return parsed


def fetch_agreed_beacon(round_num: int, fetcher: Fetcher) -> tuple[dict, dict]:
    """Fetch quicknet from api.drand.sh and api2.drand.sh.

    If both answer, they must carry the same signature and randomness.
    If only one answers, that beacon is used and the miss is recorded.
    """
    alt = DRAND_URL.replace("https://api.drand.sh/", "https://api2.drand.sh/")
    found = []
    errors = []
    for base in (DRAND_URL, alt):
        try:
            found.append(fetch_beacon(round_num, fetcher, base_url=base))
        except Exception as exc:
            errors.append(f"{base}: {exc}")
    if not found:
        raise RuntimeError("no beacon relay responded: " + "; ".join(errors))
    if len(found) == 2 and (
        found[0].get("signature") != found[1].get("signature")
        or str(found[0].get("randomness")).lower() != str(found[1].get("randomness")).lower()
    ):
        raise RuntimeError("drand relays disagree on signature or randomness")
    return found[0], {"relays_ok": len(found), "relay_errors": errors}


def tle_decrypt(armor: bytes) -> tuple[int, bytes, str]:
    try:
        proc = subprocess.run(
            [TLE, "-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
            input=armor,
            capture_output=True,
            check=False,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return 124, b"", "tle beacon/decryption timed out after 180 seconds"
    except FileNotFoundError as exc:
        return 127, b"", f"tle not found: {exc}"
    except OSError as exc:
        return 127, b"", f"tle failed to start: {exc}"
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", errors="replace")


def js_decrypt(armor: bytes, dest: Path) -> tuple[int, bytes, str]:
    dest.mkdir(parents=True, exist_ok=True)
    src = dest / "armor.tlock"
    out = dest / "js-plain.bin"
    src.write_bytes(armor)
    try:
        proc = subprocess.run(
            ["node", str(ROOT / "tools" / "tlock_decrypt.mjs"), str(src), str(out)],
            capture_output=True,
            check=False,
            cwd=str(ROOT),
        )
    except FileNotFoundError as exc:
        return 127, b"", f"node not found: {exc}"
    except OSError as exc:
        return 127, b"", f"node failed to start: {exc}"
    text = (proc.stdout + proc.stderr).decode("utf-8", errors="replace")
    if proc.returncode == 0 and out.exists():
        return 0, out.read_bytes(), text
    return proc.returncode or 1, b"", text


def committed_valid(manifest_flag: str, ciphertext_flag: str) -> bool | None:
    """True only when both inclusions are proven before unlock.

    A missing timestamp is None, not False. False is reserved for a block
    timestamp that is after unlock. Scoring still runs in every case.
    """
    if manifest_flag == "FAIL" or ciphertext_flag == "FAIL":
        return False
    if manifest_flag == "PASS" and ciphertext_flag == "PASS":
        return True
    return None


def safe_observe(txid: str, expected: str, fetcher: Fetcher) -> dict:
    """Inclusion observation must not abort a release that already decrypted."""
    try:
        return observe_item(txid, expected, fetcher)
    except Exception as exc:
        return {
            "txid": txid,
            "expected_sha256": expected,
            "turbo": None,
            "l1": None,
            "block": None,
            "payload": None,
            "error": f"observe exception: {exc}",
        }


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
    download_deadline_at = download_deadline(time.time(), int(manifest["unlock_unix"]))
    download_error = None
    while time.time() < download_deadline_at:
        try:
            got = fetch_matching(cipher_id, expected_cipher, fetcher)
            break
        except Exception as exc:
            download_error = str(exc)
            print(f"RELEASE download wait {download_error[:300]}", flush=True)
            time.sleep(60)
    if got is None:
        print(f"RELEASE_FAIL download {download_error}")
        return 2
    armor = got["body"]
    if _sha256(armor) != expected_cipher:
        raise RuntimeError("downloaded ciphertext hash mismatch")
    beacon = None
    beacon_meta = {"relays_ok": 0, "relay_errors": []}
    last_error = None
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        try:
            beacon, beacon_meta = fetch_agreed_beacon(manifest["release_round"], fetcher)
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
    manifest_obs = safe_observe(manifest_id, _sha256((directory / "manifest.json").read_bytes()), fetcher)
    cipher_obs = safe_observe(cipher_id, expected_cipher, fetcher)
    (directory / "inclusion_manifest.json").write_text(json.dumps(manifest_obs, indent=2, sort_keys=True) + "\n")
    (directory / "inclusion_ciphertext.json").write_text(json.dumps(cipher_obs, indent=2, sort_keys=True) + "\n")
    m_flag = before_unlock(manifest_obs, manifest["unlock_unix"])
    c_flag = before_unlock(cipher_obs, manifest["unlock_unix"])
    valid = committed_valid(m_flag, c_flag)
    if valid is True:
        note = (
            f"Manifest bundle L1 timestamp {manifest_obs['block']['timestamp_utc']} and "
            f"ciphertext bundle L1 timestamp {cipher_obs['block']['timestamp_utc']} are before "
            f"{manifest['unlock_utc']}. L1 status source manifest={manifest_obs['l1']['source']} "
            f"ciphertext={cipher_obs['l1']['source']}."
        )
    elif valid is False:
        note = (
            f"Inclusion before unlock is manifest={m_flag} ciphertext={c_flag}. "
            "The batch is INVALID under the reporting policy and is still scored."
        )
    else:
        note = (
            f"Inclusion before unlock is manifest={m_flag} ciphertext={c_flag}. "
            "Observation did not prove inclusion or exclusion. The batch is still scored. "
            "Validity is not decided until a later verifier observation."
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
        "beacon_relays_ok": beacon_meta.get("relays_ok"),
        "beacon_relay_errors": beacon_meta.get("relay_errors"),
        "beacon_binding": "randomness == sha256(signature); seed still uses the randomness field",
        "js_decrypt_match": js_match,
        "js_decrypt_note": js_text[-400:],
        "download_gateways": got["gateways"],
        "payload_in_bundle_manifest": (manifest_obs.get("payload") or {}).get("ok"),
        "payload_in_bundle_ciphertext": (cipher_obs.get("payload") or {}).get("ok"),
    }
    (directory / "release.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"RELEASE_OK items={len(items)} qsha={qhash} valid={valid} js_match={js_match}")
    return 0
