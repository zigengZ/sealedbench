"""SHA-256 counter-mode PRNG. No random module, no hash-order dependence."""

from __future__ import annotations

import hashlib


class PRNG:
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
        space = 1 << 64
        limit = space - (space % n)
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
        for index in range(k):
            pick = index + self.randbelow(len(pool) - index)
            pool[index], pool[pick] = pool[pick], pool[index]
        return pool[:k]

    def shuffle(self, seq) -> list:
        pool = list(seq)
        for index in range(len(pool) - 1, 0, -1):
            pick = self.randbelow(index + 1)
            pool[index], pool[pick] = pool[pick], pool[index]
        return pool
