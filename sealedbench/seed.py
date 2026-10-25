"""Seed rule for a sealed batch.

The manifest stores SEED_RULE verbatim. Hex fields are lowercased and round is
decimal ASCII with no padding. The four pieces are concatenated as bytes and
hashed with SHA-256. seed_bytes is the raw digest, not the hex text.
"""

from __future__ import annotations

import hashlib
import re

SEED_RULE = (
    'seed_hex = SHA-256( "sealedbench/v1" || chain_hash_hex || ascii(round) || randomness_hex )'
)

_HEX = re.compile(r"^[0-9a-fA-F]+$")


def seed_bytes(chain_hash_hex: str, round_num: int, randomness_hex: str) -> bytes:
    chain = chain_hash_hex.strip().lower()
    random_hex = randomness_hex.strip().lower()
    if not _HEX.fullmatch(chain) or not _HEX.fullmatch(random_hex):
        raise ValueError("chain hash and randomness must be hex")
    if int(round_num) < 1:
        raise ValueError("round must be positive")
    material = (
        "sealedbench/v1" + chain + str(int(round_num)) + random_hex
    ).encode("ascii")
    return hashlib.sha256(material).digest()


def seed_hex(chain_hash_hex: str, round_num: int, randomness_hex: str) -> str:
    return seed_bytes(chain_hash_hex, round_num, randomness_hex).hex()
