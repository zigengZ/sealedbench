#!/usr/bin/env python3
"""Seed spec, PRNG, canonical JSON, strict grader, and the code interpreter."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest

from sealedbench.v2.families.code_output import BUILDERS, execute
from sealedbench.v2.generate import ARITH_TEMPLATES, generate_batch, template_bank
from sealedbench.v2.grade import extract_strict_integer, grade_answer, is_truncated
from sealedbench.v2.prng import PRNG
from sealedbench.v2.spec import TEST_SECRET, canon, derive_seed, enc, family_seed
from sealedbench.v2.stats import newcombe, wilson


class SpecTests(unittest.TestCase):
    def test_length_prefix_is_unambiguous(self):
        self.assertEqual(enc([b"ab", b"c"]), b"\x00\x00\x00\x02ab\x00\x00\x00\x01c")

    def test_seed_uses_signature_bytes_not_randomness_text(self):
        signature = bytes.fromhex("aa" * 48)
        secret = TEST_SECRET
        chain = "ab" * 32
        first = derive_seed(chain, 1000, signature, secret)
        second = derive_seed(chain.upper(), "1000", signature, secret)
        self.assertEqual(first, second)
        material = enc(
            [
                b"sealedbench/v2",
                chain.encode("ascii"),
                b"1000",
                signature,
                secret,
            ]
        )
        self.assertEqual(first, hashlib.sha256(material).digest())
        other = derive_seed(chain, 1000, signature + b"\x00", secret)
        self.assertNotEqual(first, other)
        with self.assertRaises(ValueError):
            derive_seed(chain, 1000, signature, b"short")

    def test_family_seed_depends_on_n(self):
        seed = b"s" * 32
        self.assertNotEqual(family_seed(seed, "arith_word", 80), family_seed(seed, "arith_word", 81))

    def test_canonical_json(self):
        self.assertEqual(canon({"b": 1, "a": "é"}), '{"a":"\\u00e9","b":1}')

    def test_prng_is_stable_and_not_constant(self):
        left = PRNG(b"\x01" * 32)
        right = PRNG(b"\x01" * 32)
        draws = [left.randint(0, 10**6) for _ in range(8)]
        self.assertEqual(draws, [right.randint(0, 10**6) for _ in range(8)])
        self.assertGreater(len(set(draws)), 1)


class GradeTests(unittest.TestCase):
    def test_no_bare_number_fallback(self):
        graded = grade_answer("arith_word", "6", "The total is 6.\n")
        self.assertTrue(graded.invalid)
        self.assertFalse(graded.correct)
        self.assertIsNone(graded.parsed)

    def test_last_hash_line(self):
        graded = grade_answer("arith_word", "10", "#### 4\nthinking\n#### 10\n")
        self.assertTrue(graded.correct)
        self.assertEqual(graded.parsed, "10")

    def test_truncated_is_invalid_even_with_hash(self):
        graded = grade_answer("graph_path", "6", "#### 6\n", truncated=True)
        self.assertTrue(graded.invalid)
        self.assertTrue(graded.truncated)
        self.assertFalse(graded.correct)

    def test_code_uses_last_fence_only(self):
        raw = "```\nwrong\n```\n```\n1\n2\n```\n"
        graded = grade_answer("code_output", "1\n2", raw)
        self.assertTrue(graded.correct)
        graded_missing = grade_answer("code_output", "1", "1")
        self.assertTrue(graded_missing.invalid)

    def test_truncation_detector(self):
        self.assertTrue(is_truncated("#### 3", 100, 768))
        self.assertFalse(is_truncated("#### 3 [end of text]", 100, 768))
        self.assertTrue(is_truncated("#### 3 [end of text]", 767, 768))

    def test_strict_regex_rejects_trailing_words(self):
        self.assertIsNone(extract_strict_integer("#### 12 apples"))


class CodeOracleTests(unittest.TestCase):
    def test_interpreter_matches_cpython(self):
        rng = PRNG(b"oracle-check")
        for name, builder in BUILDERS.items():
            source = builder(rng)
            got, err = execute(source)
            self.assertEqual(err, "", name)
            proc = subprocess.run(
                [sys.executable, "-I", "-c", source],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            expected = proc.stdout.replace("\r\n", "\n").rstrip("\n")
            self.assertEqual(got, expected, name)

    def test_step_budget_rejects_without_a_clock(self):
        source = "total = 0\nfor value in range(4):\n    total = total + value\nprint(total)\n"
        text, err = execute(source, budget=3)
        self.assertIsNone(text)
        self.assertNotEqual(err, "")


class GenerateTests(unittest.TestCase):
    def test_small_batch_is_deterministic(self):
        signature = hashlib.sha256(b"vector").digest()
        seed = derive_seed("cd" * 32, 1000, signature, TEST_SECRET)
        counts = {"arith_word": 4, "code_output": 4, "graph_path": 4}
        first = generate_batch(seed, counts)
        second = generate_batch(seed, counts)
        self.assertEqual([item.to_json_line() for item in first], [item.to_json_line() for item in second])
        self.assertEqual([item.item_id for item in first[:3]], ["arith_word-0000", "arith_word-0001", "arith_word-0002"])
        templates = {item.params["template_id"] for item in first if item.family == "code_output"}
        self.assertTrue(templates)
        self.assertEqual(len(ARITH_TEMPLATES), 25)
        bank = template_bank()
        self.assertEqual(len(bank["code_output"]), 8)
        encoded = json.dumps(bank, sort_keys=True)
        self.assertIn("acc", encoded)

    def test_wilson_and_newcombe(self):
        lo, hi = wilson(40, 80)
        self.assertLess(lo, 0.5)
        self.assertGreater(hi, 0.5)
        diff, low, high = newcombe(50, 80, 40, 80)
        self.assertAlmostEqual(diff, 0.125)
        self.assertLess(low, diff)
        self.assertGreater(high, diff)


if __name__ == "__main__":
    unittest.main()
