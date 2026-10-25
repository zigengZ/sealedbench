"""Build a v2 manifest. The ciphertext is uploaded before this runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sealedbench.protocol import (
    BUILD_FLAGS,
    CHAIN_HASH,
    CHAIN_PUBKEY,
    GENESIS,
    LLAMA_BINARY,
    LLAMA_BINARY_SHA256,
    LLAMA_COMMIT,
    LLAMA_TAG,
    MODELS,
    PERIOD_S,
    SCHEME,
    SYSTEM_PROMPTS,
)
from sealedbench.v2.constants import COUNTS, N_PREDICT, REPORTING
from sealedbench.v2.spec import canon
from sealedbench.v2.tarball import GRADER_FILES, grader_sha256, template_bank_bytes

SEED_SPEC = (
    "enc(b) = uint32be(len(b)) || b. "
    "seed = SHA-256(enc(utf8('sealedbench/v2')) || enc(utf8(lowercase chain hash hex)) "
    "|| enc(utf8(decimal round)) || enc(signature bytes) || enc(32-byte batch secret)). "
    "family_seed = SHA-256(enc(utf8('sealedbench/v2/family')) || enc(seed) || "
    "enc(utf8(family)) || enc(utf8(decimal n))). "
    "The JSON randomness field is not an input. It must still equal hex(SHA-256(signature))."
)


def _libs(binary: Path) -> list[dict]:
    import subprocess

    proc = subprocess.run(["ldd", str(binary)], text=True, capture_output=True, check=False)
    rows = []
    if proc.returncode != 0:
        return rows
    for line in proc.stdout.splitlines():
        if "=>" not in line:
            continue
        name, rest = line.strip().split("=>", 1)
        path = rest.strip().split()[0]
        if path == "not":
            continue
        lib = Path(path)
        if not lib.is_file():
            continue
        if not any(token in lib.name for token in ("libllama", "libggml")):
            continue
        data = lib.read_bytes()
        rows.append({"name": lib.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    rows.sort(key=lambda row: row["name"])
    return rows


def build_manifest(
    root: Path,
    batch_id: str,
    release_round: int,
    unlock_unix: int,
    unlock_utc: str,
    peer_id: str,
    peer_ciphertext_sha256: str,
    ciphertext_txid: str,
    ciphertext_sha256: str,
    ciphertext_bytes: int,
    plaintext_sha256: str,
    plaintext_bytes: int,
    reference_txid: str,
    reference_sha256: str,
    reference_bytes: int,
    vectors: list[dict],
) -> dict:
    bank = template_bank_bytes()
    binary = Path(LLAMA_BINARY)
    runtime = {
        "llama_cpp_tag": LLAMA_TAG,
        "llama_cpp_commit": LLAMA_COMMIT,
        "build_flags": list(BUILD_FLAGS),
        "binary_path": LLAMA_BINARY,
        "binary_sha256": LLAMA_BINARY_SHA256,
        "binary_bytes": binary.stat().st_size if binary.is_file() else None,
        "binary_note": "The executable is the launcher. shared_libraries are the hashed compute code.",
        "shared_libraries": _libs(binary) if binary.is_file() else [],
        "threads": 6,
        "threads_batch": 6,
        "batch": 2048,
        "ubatch": 512,
        "seed": 42,
        "ctx": 2048,
        "n_predict": dict(N_PREDICT),
        "n_predict_note": (
            "Phase 1 at n_predict 320 truncated 20/200 GSM8K completions "
            "(Qwen 5/50, Gemma 5/50, Ministral 2/50, Falcon 8/50) and the hit_cap flag was always false. "
            "EOS maxima were 292 to 318. 768 is above that observed maximum. "
            "The truncation rate at 768 was not measured, because those 20 completions were censored."
        ),
        "temp": 0,
        "top_k": 1,
        "top_p": 1,
        "min_p": 0,
        "repeat_penalty": 1,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "reasoning": "off",
        "reasoning_note": "Qwen3-4B-Instruct-2507 is the non-thinking variant. reasoning off is a parser flag, not a capability switch.",
        "jinja": True,
        "prompt_cache": False,
        "env": {"GOMP_SPINCOUNT": "0", "OMP_NUM_THREADS": "6"},
        "extra_args": [
            "--no-warmup",
            "--single-turn",
            "--no-display-prompt",
            "--color",
            "off",
            "--log-colors",
            "off",
            "--no-log-prefix",
        ],
    }
    return {
        "protocol_version": "sealedbench/v2",
        "app_version": "0.2.0",
        "batch_id": batch_id,
        "release_round": release_round,
        "unlock_unix": unlock_unix,
        "unlock_utc": unlock_utc,
        "drand": {
            "chain_hash": CHAIN_HASH,
            "public_key": CHAIN_PUBKEY,
            "scheme": SCHEME,
            "genesis_unix": GENESIS,
            "period_s": PERIOD_S,
            "beacon_url_template": f"https://api.drand.sh/{CHAIN_HASH}/public/{{round}}",
        },
        "seed_spec": SEED_SPEC,
        "spec": {
            "seed": SEED_SPEC,
            "test_secret_hex": "0123456789abcdef" * 4,
            "test_secret_note": "The published test secret is not the batch secret. Vectors do not predict this batch.",
            "author_limitation": (
                "The author chose the 32-byte batch secret and knows it. "
                "The author does not know the beacon signature, so the author cannot list the items before the round. "
                "Publishing this repository does not reveal the items."
            ),
            "test_vectors": vectors,
            "canonical_json": "json.dumps(sort_keys=True, separators=(',', ':'), ensure_ascii=True) plus a trailing newline per item.",
            "prng": "SHA-256(key || uint64be(counter)), counter from 0, rejection sampling on the first 8 bytes.",
        },
        "ciphertext": {
            "txid": ciphertext_txid,
            "sha256": ciphertext_sha256,
            "bytes": ciphertext_bytes,
            "armor": True,
            "tool": "github.com/drand/tlock/cmd/tle@v1.2.0",
        },
        "plaintext_tarball_sha256": plaintext_sha256,
        "plaintext_tarball_bytes": plaintext_bytes,
        "peer": {"batch_id": peer_id, "ciphertext_sha256": peer_ciphertext_sha256},
        "generator": {
            "families": [{"name": name, "n": COUNTS[name]} for name in ("arith_word", "code_output", "graph_path")],
            "item_ordering": "arith_word, code_output, graph_path. item_id is '{family}-{index:04d}'.",
            "code_oracle": "AST interpreter, step budget 10000, no subprocess and no wall clock.",
            "python": "3.12",
        },
        "grader": {
            "files": list(GRADER_FILES),
            "sha256": grader_sha256(root),
            "integer_rule": "last line matching ^####[ \\t]+(-?\\d[\\d,]*)[ \\t]*$; no bare-number fallback",
            "code_rule": "last fenced block; rstrip each line; drop one trailing empty line",
            "invalid_policy": "unparsable or truncated is invalid and counts as wrong in the primary accuracy",
        },
        "template_bank_sha256": hashlib.sha256(bank).hexdigest(),
        "template_bank_bytes": len(bank),
        "reference": {
            "txid": reference_txid,
            "sha256": reference_sha256,
            "bytes": reference_bytes,
            "n": 80,
            "indexes": "0..79",
            "dataset": "GSM8K-test",
        },
        "models": [
            {
                "id": row["id"],
                "file": row["file"],
                "sha256": row["sha256"],
                "url": row["url"],
                "rendered_prompt_sha256": row["rendered_prompt_sha256"],
            }
            for row in MODELS
        ],
        "system_prompts": dict(SYSTEM_PROMPTS),
        "runtime": runtime,
        "reporting": REPORTING,
        "counts_note": "220 completions per model: 80 arith + 30 code + 30 graph + 80 reference.",
    }


def dumps_manifest(doc: dict) -> bytes:
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode("utf-8")


def manifest_sha256(doc: dict) -> str:
    return hashlib.sha256(dumps_manifest(doc)).hexdigest()

def build_b3_manifest(
    root: Path,
    batch_id: str,
    release_round: int,
    unlock_unix: int,
    unlock_utc: str,
    ciphertext_txid: str,
    ciphertext_sha256: str,
    ciphertext_bytes: int,
    plaintext_sha256: str,
    plaintext_bytes: int,
    reference_txid: str,
    reference_sha256: str,
    reference_bytes: int,
    vectors: list[dict],
    *,
    role: str = "b3",
    peer_batch_id: str | None = None,
    peer_ciphertext_sha256: str | None = None,
):
    """b2 manifest shape, plus the b3 grader-input normalization.

    role 'b3' declares the sealed b2 and cap2 ciphertexts.
    role 'cap3' declares cap2 and, when given, names b3 as its peer.
    """
    from sealedbench.v2.constants import (
        B2_CIPHERTEXT_SHA256,
        B3_CORRECTION,
        B3_GRADER_FILES,
        B3_N_PREDICT,
        B3_N_PREDICT_NOTE,
        CAP2_CIPHERTEXT_SHA256,
        CAP3_CORRECTION,
    )
    from sealedbench.v2.grade_b3 import NORMALIZATION_SPEC
    from sealedbench.v2.tarball import grader_sha256 as hash_grader

    if role == "b3":
        peer_batch_id = peer_batch_id or "b2"
        peer_ciphertext_sha256 = peer_ciphertext_sha256 or B2_CIPHERTEXT_SHA256
        declared = [
            {"batch_id": "b2", "ciphertext_sha256": B2_CIPHERTEXT_SHA256},
            {"batch_id": "cap2", "ciphertext_sha256": CAP2_CIPHERTEXT_SHA256},
        ]
        statement = B3_CORRECTION
    elif role == "cap3":
        peer_batch_id = peer_batch_id or "b3"
        if not peer_ciphertext_sha256:
            raise ValueError("cap3 requires the b3 ciphertext sha256")
        declared = [
            {"batch_id": "cap2", "ciphertext_sha256": CAP2_CIPHERTEXT_SHA256},
        ]
        statement = CAP3_CORRECTION
    else:
        raise ValueError(f"unknown b3 role {role}")

    doc = build_manifest(
        root,
        batch_id=batch_id,
        release_round=release_round,
        unlock_unix=unlock_unix,
        unlock_utc=unlock_utc,
        peer_id=peer_batch_id,
        peer_ciphertext_sha256=peer_ciphertext_sha256,
        ciphertext_txid=ciphertext_txid,
        ciphertext_sha256=ciphertext_sha256,
        ciphertext_bytes=ciphertext_bytes,
        plaintext_sha256=plaintext_sha256,
        plaintext_bytes=plaintext_bytes,
        reference_txid=reference_txid,
        reference_sha256=reference_sha256,
        reference_bytes=reference_bytes,
        vectors=vectors,
    )
    doc["grader"]["files"] = list(B3_GRADER_FILES)
    doc["grader"]["sha256"] = hash_grader(root, B3_GRADER_FILES)
    doc["grader"]["input_normalization"] = NORMALIZATION_SPEC
    doc["grader"]["truncation"] = (
        "Unchanged from b2. A completion is truncated when the raw stdout does not contain "
        "[end of text], or when the llama.cpp run count is at least n_predict-1. "
        "The input normalization is not applied before that check."
    )
    doc["runtime"]["n_predict"] = dict(B3_N_PREDICT)
    doc["runtime"]["n_predict_note"] = B3_N_PREDICT_NOTE
    doc["corrects"] = {"statement": statement, "declared": declared}
    return doc
