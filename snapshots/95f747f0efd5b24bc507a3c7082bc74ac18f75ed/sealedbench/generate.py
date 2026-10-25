"""Build a batch from one 32-byte seed.

family_seed = SHA-256(
    ASCII("sealedbench/v1/family\\n") || seed_bytes || ASCII("\\n")
    || ASCII(family) || ASCII("\\n") || ASCII(n)
)
Families are emitted in FAMILY_ORDER. item_id is "{family}-{index:04d}".
"""

from __future__ import annotations

import hashlib

from sealedbench.families import GENERATORS
from sealedbench.items import Item

FAMILY_ORDER = ("arith_word", "code_output", "graph_path")

ITEM_ORDERING = (
    "Families run in the order arith_word, code_output, graph_path. "
    "item_id is '{family}-{index:04d}' starting at 0 inside the family. "
    "family_seed = SHA-256(ASCII('sealedbench/v1/family\\n') || seed_bytes || "
    "ASCII('\\n') || ASCII(family) || ASCII('\\n') || ASCII(n)), where seed_bytes "
    "is the raw 32-byte digest from the seed rule. Candidates are drawn in RNG "
    "order and rejected when they are degenerate (integer answer 0, empty program "
    "output, a one-edge shortest path), when the prompt was already kept, or when "
    "a program errors or times out. The first n accepted candidates form the family."
)


def family_seed(seed: bytes, family: str, n: int) -> bytes:
    if family not in FAMILY_ORDER:
        raise ValueError(family)
    return hashlib.sha256(
        b"sealedbench/v1/family\n"
        + bytes(seed)
        + b"\n"
        + family.encode("ascii")
        + b"\n"
        + str(int(n)).encode("ascii")
    ).digest()


def generate_batch(seed: bytes, counts: dict) -> list[Item]:
    if set(counts) != set(FAMILY_ORDER):
        raise ValueError(f"counts must name {FAMILY_ORDER}")
    items: list[Item] = []
    seen: set[str] = set()
    for family in FAMILY_ORDER:
        n = int(counts[family])
        if n < 0:
            raise ValueError("n must be >= 0")
        produced = GENERATORS[family](family_seed(seed, family, n), n)
        if len(produced) != n:
            raise RuntimeError(f"{family} returned {len(produced)} items, wanted {n}")
        for item in produced:
            if item.family != family or item.prompt in seen:
                raise RuntimeError(f"duplicate or mismatched item {item.item_id}")
            seen.add(item.prompt)
            items.append(item)
    return items
