#!/usr/bin/env python3
"""Seal b2 and cap2 locally. Does not upload.

Secrets stay in /root/sbw/p2r/secrets (mode 0600) and inside the ciphertext.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.constants import BATCHES, COUNTS  # noqa: E402
from sealedbench.v2.diversity import gate_sealed_bytes  # noqa: E402
from sealedbench.v2.reference_set import build_reference  # noqa: E402
from sealedbench.v2.spec import CHAIN_HASH, TEST_SECRET, derive_seed, randomness_hex  # noqa: E402
from sealedbench.v2.tarball import build_v2_tarball, sha256  # noqa: E402

SECRETS = Path("/root/sbw/p2r/secrets")
TLE = os.environ.get("TLE", "/root/.cache/sealedbench/gopath/bin/tle")
VECTOR_ROUNDS = [1000, 1_000_000, 33_000_000]


def load_secret(batch: str) -> bytes:
    SECRETS.mkdir(parents=True, exist_ok=True)
    path = SECRETS / f"{batch}.bin"
    if path.exists():
        data = path.read_bytes()
        if len(data) != 32:
            raise SystemExit(f"{path} is not 32 bytes")
        return data
    data = os.urandom(32)
    path.write_bytes(data)
    path.chmod(0o600)
    return data


def encrypt(plain: bytes, round_num: int) -> tuple[int, bytes, str]:
    proc = subprocess.run(
        [TLE, "-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", str(round_num), "-a"],
        input=plain,
        capture_output=True,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr.decode("utf-8", errors="replace")


def go_decrypt(armor: bytes) -> tuple[int, str]:
    proc = subprocess.run(
        [TLE, "-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
        input=armor,
        capture_output=True,
        check=False,
    )
    err = proc.stderr.decode("utf-8", errors="replace")
    return proc.returncode, err


def js_decrypt(path: Path) -> tuple[int, str]:
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "v2_early_decrypt.mjs"), str(path)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    return proc.returncode, (proc.stdout + proc.stderr)[-400:]


def fetch_beacon(round_num: int) -> dict:
    url = f"https://api.drand.sh/{CHAIN_HASH}/public/{round_num}"
    with urllib.request.urlopen(url, timeout=60) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if int(body["round"]) != round_num:
        raise RuntimeError("round mismatch")
    signature = bytes.fromhex(body["signature"])
    if randomness_hex(signature) != body["randomness"]:
        raise RuntimeError("randomness is not sha256(signature)")
    proc = subprocess.run(
        ["node", str(ROOT / "tools" / "verify_beacon.mjs")],
        input=json.dumps({"round": round_num, "beacon": body}).encode(),
        capture_output=True,
        check=False,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode()[-300:] or proc.stdout.decode()[-300:])
    return body


def make_vectors() -> list[dict]:
    from sealedbench.items import question_set_sha256
    from sealedbench.v2.generate import generate_batch

    vectors = []
    for round_num in VECTOR_ROUNDS:
        beacon = fetch_beacon(round_num)
        signature = bytes.fromhex(beacon["signature"])
        seed = derive_seed(CHAIN_HASH, round_num, signature, TEST_SECRET)
        items = generate_batch(seed, COUNTS)
        vectors.append(
            {
                "round": round_num,
                "signature_sha256": hashlib.sha256(signature).hexdigest(),
                "signature_hex": beacon["signature"],
                "randomness": beacon["randomness"],
                "seed_hex": seed.hex(),
                "counts": dict(COUNTS),
                "first_item_ids": [item.item_id for item in items[:3]],
                "first_prompt_sha256": [
                    hashlib.sha256(item.prompt.encode("utf-8")).hexdigest() for item in items[:3]
                ],
                "question_set_sha256": question_set_sha256(items),
            }
        )
        print(f"vector round {round_num} ids={vectors[-1]['first_item_ids']}", flush=True)
    return vectors


def self_check(tarball: bytes) -> str:
    import gzip
    import io
    import tarfile
    import tempfile

    raw = gzip.decompress(tarball)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            tar.extractall(dest)
        script = (
            "import json, sys\n"
            "from sealedbench.v2.secret import load_secret\n"
            "from sealedbench.v2.spec import derive_seed\n"
            "from sealedbench.v2.generate import generate_batch\n"
            "secret = load_secret()\n"
            "if len(secret) != 32:\n"
            "    raise SystemExit('secret length')\n"
            "seed = derive_seed(sys.argv[1], 1000, bytes.fromhex(sys.argv[2]), secret)\n"
            "items = generate_batch(seed, json.loads(sys.argv[3]))\n"
            "print(len(items))\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(dest)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-c", script, CHAIN_HASH, "ab" * 32, json.dumps({"arith_word": 1, "code_output": 1, "graph_path": 1})],
            cwd=str(dest),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-1500:])
        return proc.stdout.strip()


def main() -> None:
    secrets = {batch: load_secret(batch) for batch in ("b2", "cap2")}
    if secrets["b2"] == secrets["cap2"]:
        raise SystemExit("b2 and cap2 secrets must differ")
    tarballs = {batch: build_v2_tarball(ROOT, secret) for batch, secret in secrets.items()}
    for batch, blob in tarballs.items():
        if len(blob) > 100 * 1024:
            raise SystemExit(f"{batch} tarball {len(blob)} exceeds 100 KiB")
        print(f"{batch} tarball bytes={len(blob)} sha256={sha256(blob)}", flush=True)
    print(self_check(tarballs["b2"]), flush=True)
    print("diversity gate on sealed bytes", flush=True)
    report = gate_sealed_bytes(tarballs["b2"], 1000)
    if not report.get("gate_pass"):
        raise SystemExit(f"diversity gate failed {json.dumps(report)[:500]}")
    print(
        f"diversity sets={report['distinct_question_sets']} "
        f"arith_share={report['worst_max_share_arith']} code_share={report['worst_max_share_code']}",
        flush=True,
    )
    (ROOT / "results" / "batches" / "b2").mkdir(parents=True, exist_ok=True)
    (ROOT / "results" / "batches" / "b2" / "diversity.json").write_text(json.dumps(report, indent=2) + "\n")

    cipher = {}
    early = {}
    for batch, spec in BATCHES.items():
        code, armor, err = encrypt(tarballs[batch], spec["release_round"])
        if code != 0 or len(armor) < 80:
            raise SystemExit(f"encrypt {batch} failed {code} {err[-300:]}")
        dest = ROOT / "results" / "batches" / batch
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / "generator.tlock"
        path.write_bytes(armor)
        go_code, go_err = go_decrypt(armor)
        js_code, js_text = js_decrypt(path)
        if go_code == 0 or js_code != 0:
            raise SystemExit(f"early decrypt did not refuse {batch} go={go_code} js={js_code} {js_text}")
        cipher[batch] = {"sha256": sha256(armor), "bytes": len(armor), "plaintext_sha256": sha256(tarballs[batch]), "plaintext_bytes": len(tarballs[batch])}
        early[batch] = {"go_exit": go_code, "go_stderr": go_err[-300:], "js": js_text.strip()}
        print(f"sealed {batch} cipher={cipher[batch]['sha256']} early_go={go_code}", flush=True)

    reference = build_reference(ROOT)
    ref_path = ROOT / "results" / "batches" / "b2" / "reference.json"
    ref_path.write_bytes(reference["file_bytes"])
    if hashlib.sha256(ref_path.read_bytes()).hexdigest() != reference["file_sha256"]:
        raise SystemExit("reference bytes drifted")
    if reference["file_bytes"].__len__() > 100 * 1024:
        raise SystemExit("reference over 100 KiB")
    print(f"reference bytes={len(reference['file_bytes'])} sha256={reference['file_sha256']}", flush=True)

    vectors = make_vectors()
    (ROOT / "sealedbench" / "v2" / "vectors.json").write_text(json.dumps(vectors, indent=2) + "\n")
    record = {
        "ciphertext": cipher,
        "early_decrypt": early,
        "reference_sha256": reference["file_sha256"],
        "reference_bytes": len(reference["file_bytes"]),
        "diversity_gate_pass": True,
        "vector_rounds": VECTOR_ROUNDS,
    }
    (ROOT / "results" / "batches" / "b2" / "prepare.json").write_text(json.dumps(record, indent=2) + "\n")
    print("PREPARE_OK", flush=True)


if __name__ == "__main__":
    main()
