#!/usr/bin/env python3
"""A 404/429 must not become a verify FAIL."""

from __future__ import annotations

import inspect
import unittest

import sealedbench.verify as verify
from sealedbench.release import FetchError


class VerifyHotfixTests(unittest.TestCase):
    def test_source_no_longer_promotes_unknown_inclusion_to_fail(self):
        source = inspect.getsource(verify.verify_index)
        self.assertNotIn("UNKNOWN inclusion for a batch marked valid", source)

    def test_unknown_inclusion_stays_unknown_even_if_batch_claims_valid(self):
        self.assertEqual(verify.classify_inclusion("UNKNOWN", claimed_valid=True), "UNKNOWN")
        self.assertEqual(verify.classify_inclusion("PASS", claimed_valid=True), "PASS")
        self.assertEqual(verify.classify_inclusion("FAIL", claimed_valid=False), "FAIL")

    def test_unavailable_fetch_is_unknown_and_mismatch_is_fail(self):
        missing = FetchError("no host", hits=[], kind="unavailable")
        wrong = FetchError("bad hash", hits=[], kind="mismatch")
        self.assertEqual(verify.classify_fetch_error(missing), "UNKNOWN")
        self.assertEqual(verify.classify_fetch_error(wrong), "FAIL")

    def test_gateway_404_is_not_a_served_failure(self):
        hits = [
            {"host": "https://arweave.net", "http": 429, "sha256": None, "match": False},
            {"host": "https://ar-io.dev", "http": 404, "sha256": None, "match": False},
            {"host": "https://turbo-gateway.com", "http": 200, "sha256": "aa", "match": True},
        ]
        self.assertEqual(verify.classify_gateway_hits(hits), "PASS")
        only_errors = [
            {"host": "https://arweave.net", "http": 429, "sha256": None, "match": False},
            {"host": "https://ar-io.dev", "http": 404, "sha256": None, "match": False},
        ]
        self.assertEqual(verify.classify_gateway_hits(only_errors), "UNKNOWN")
        contradiction = [
            {"host": "https://ar-io.dev", "http": 200, "sha256": "nope", "match": False},
        ]
        self.assertEqual(verify.classify_gateway_hits(contradiction), "FAIL")

    def test_payload_http_error_is_unknown(self):
        self.assertEqual(verify.classify_payload({"ok": False, "http": 404, "sha256": "ab"}), "UNKNOWN")
        self.assertEqual(verify.classify_payload({"ok": False, "http": 429, "sha256": "ab"}), "UNKNOWN")
        self.assertEqual(
            verify.classify_payload({"ok": False, "http": 200, "sha256": "ab", "got_bytes": 4}),
            "FAIL",
        )
        self.assertEqual(verify.classify_payload({"ok": True, "http": 206, "sha256": "ab"}), "PASS")

    def test_result_exit_codes(self):
        self.assertEqual(verify.result_exit([("a", "PASS", "")]), ("PASS", 0))
        self.assertEqual(verify.result_exit([("a", "UNKNOWN", "")]), ("UNKNOWN", 2))
        self.assertEqual(verify.result_exit([("a", "FAIL", "")]), ("FAIL", 1))
        self.assertEqual(verify.result_exit([("a", "REPO-ONLY", "")]), ("UNKNOWN", 2))
        self.assertEqual(verify.result_exit([("batch validity", "INVALID", "INVALID")]), ("INVALID", 2))


if __name__ == "__main__":
    unittest.main()
