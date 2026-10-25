"""Deterministic RNG used by every generator.

Each draw consumes one SHA-256 block. The block is SHA-256(key || counter)
where counter is an 8-byte big-endian integer starting at 0. Integers use the
first 8 bytes of the block and rejection sampling, so the stream does not
depend on Python's `random` module.
"""

from __future__ import annotations

import hashlib


class RNG:
    def __init__(self, seed: bytes):
        if not isinstance(seed, (bytes, bytearray)) or len(seed) == 0:
            raise ValueError("seed must be non-empty bytes")
        self.key = bytes(seed)
        self.counter = 0

    def _block(self) -> bytes:
        block = hashlib.sha256(self.key + self.counter.to_bytes(8, "big")).digest()
        self.counter += 1
        return block

    def randbelow(self, n: int) -> int:
        if n <= 0:
            raise ValueError("n must be positive")
        if n == 1:
            return 0
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            draw = int.from_bytes(self._block()[:8], "big")
            if draw < limit:
                return draw % n

    def randint(self, lo: int, hi: int) -> int:
        if hi < lo:
            raise ValueError("hi < lo")
        return lo + self.randbelow(hi - lo + 1)

    def choice(self, seq):
        if not seq:
            raise ValueError("empty sequence")
        return seq[self.randbelow(len(seq))]

    def sample(self, seq, k: int) -> list:
        pool = list(seq)
        if k < 0 or k > len(pool):
            raise ValueError("sample size out of range")
        for i in range(k):
            j = i + self.randbelow(len(pool) - i)
            pool[i], pool[j] = pool[j], pool[i]
        return pool[:k]

    def shuffle(self, seq) -> list:
        pool = list(seq)
        for i in range(len(pool) - 1, 0, -1):
            j = self.randbelow(i + 1)
            pool[i], pool[j] = pool[j], pool[i]
        return pool
