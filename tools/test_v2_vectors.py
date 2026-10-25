#!/usr/bin/env python3
"""The published test vectors reproduce from the signature bytes and the test secret."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from sealedbench.items import question_set_sha256
from sealedbench.v2.generate import generate_batch
from sealedbench.v2.spec import CHAIN_HASH, TEST_SECRET, derive_seed

ROOT = Path(__file__).resolve().parents[1]


class VectorTests(unittest.TestCase):
    def test_three_past_rounds(self):
        vectors = json.loads((ROOT / "sealedbench" / "v2" / "vectors.json").read_text())
        self.assertEqual(len(vectors), 3)
        seeds = set()
        for vector in vectors:
            signature = bytes.fromhex(vector["signature_hex"])
            self.assertEqual(hashlib.sha256(signature).hexdigest(), vector["randomness"])
            seed = derive_seed(CHAIN_HASH, vector["round"], signature, TEST_SECRET)
            self.assertEqual(seed.hex(), vector["seed_hex"])
            items = generate_batch(seed, vector["counts"])
            self.assertEqual([item.item_id for item in items[:3]], vector["first_item_ids"])
            got = [hashlib.sha256(item.prompt.encode()).hexdigest() for item in items[:3]]
            self.assertEqual(got, vector["first_prompt_sha256"])
            self.assertEqual(question_set_sha256(items), vector["question_set_sha256"])
            seeds.add(seed.hex())
        self.assertEqual(len(seeds), 3)


if __name__ == "__main__":
    unittest.main()
