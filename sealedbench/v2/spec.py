"""Byte-exact seed and canonical JSON for sealedbench/v2.

enc(b) = uint32 big-endian length || b

seed material, in order:
  enc(utf-8 "sealedbench/v2")
  enc(utf-8 lowercase chain-hash hex, 64 chars)
  enc(utf-8 decimal round, no sign and no leading zeros)
  enc(raw signature bytes)
  enc(32-byte batch secret)

seed = SHA-256(material). The JSON randomness field is not an input.
"""

from __future__ import annotations

import hashlib
import json

DOMAIN = b"sealedbench/v2"
FAMILY_DOMAIN = b"sealedbench/v2/family"
TEST_SECRET = bytes.fromhex("0123456789abcdef" * 4)

CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
GENESIS = 1692803367
PERIOD_S = 3


def enc(parts: list[bytes]) -> bytes:
    out = bytearray()
    for part in parts:
        if not isinstance(part, (bytes, bytearray)):
            raise TypeError("enc expects bytes")
        if len(part) > 0xFFFFFFFF:
            raise ValueError("part longer than uint32")
        out += len(part).to_bytes(4, "big")
        out += part
    return bytes(out)


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def randomness_hex(signature: bytes) -> str:
    return hashlib.sha256(signature).hexdigest()


def derive_seed(chain_hash_hex: str, round_num: int, signature: bytes, secret: bytes) -> bytes:
    chain = chain_hash_hex.strip().lower().encode("ascii")
    if len(chain) != 64:
        raise ValueError("chain hash must be 64 lowercase hex characters")
    bytes.fromhex(chain.decode("ascii"))
    round_int = int(round_num)
    if round_int < 1 or str(round_int).encode("ascii") != str(round_num).strip().encode("ascii"):
        raise ValueError("round must be a positive decimal integer")
    if isinstance(signature, str):
        raise TypeError("signature must be raw bytes, not hex text")
    if not signature:
        raise ValueError("signature is empty")
    if len(secret) != 32:
        raise ValueError("batch secret must be 32 bytes")
    material = enc(
        [
            DOMAIN,
            chain,
            str(round_int).encode("ascii"),
            bytes(signature),
            bytes(secret),
        ]
    )
    return hashlib.sha256(material).digest()


def family_seed(seed: bytes, family: str, n: int) -> bytes:
    if len(seed) != 32:
        raise ValueError("seed must be 32 bytes")
    return hashlib.sha256(
        enc(
            [
                FAMILY_DOMAIN,
                bytes(seed),
                family.encode("ascii"),
                str(int(n)).encode("ascii"),
            ]
        )
    ).digest()


def round_for_unix(unix: int) -> int:
    delta = int(unix) - GENESIS
    if delta % PERIOD_S != 0:
        raise ValueError("unix time is not on a quicknet boundary")
    return delta // PERIOD_S + 1


def unix_for_round(round_num: int) -> int:
    return GENESIS + (int(round_num) - 1) * PERIOD_S
