#!/usr/bin/env python3
"""Class-A release hotfixes. These assertions fail on the pre-hotfix code."""

from __future__ import annotations

import hashlib
import unittest

from sealedbench.net import Fetcher
from sealedbench.release import (
    FetchError,
    beacon_binding_error,
    committed_valid,
    download_deadline,
    fetch_matching,
    tle_decrypt,
)


class FakeFetcher:
    def __init__(self, routes: dict):
        self.routes = routes

    def get(self, url, headers=None, timeout=90, data=None):
        if url not in self.routes:
            return 0, {}, b""
        status, body = self.routes[url]
        return status, {}, body


BODY = b"cipher-bytes"
DIGEST = hashlib.sha256(BODY).hexdigest()
TX = "abc123"


def routes_for(by_host: dict) -> dict:
    return {f"{host}/{TX}": pair for host, pair in by_host.items()}


class ReleaseHotfixTests(unittest.TestCase):
    def test_any_matching_gateway_is_enough(self):
        fetcher = FakeFetcher(
            routes_for(
                {
                    "https://ar-io.dev": (404, b"missing"),
                    "https://arweave.net": (429, b"slow"),
                    "https://ario.zigza.xyz": (404, b""),
                    "https://turbo-gateway.com": (200, BODY),
                }
            )
        )
        got = fetch_matching(TX, DIGEST, fetcher)
        self.assertEqual(got["body"], BODY)

    def test_all_429_is_unavailable_not_a_hash_mismatch(self):
        fetcher = FakeFetcher(
            routes_for(
                {
                    "https://ar-io.dev": (404, b""),
                    "https://arweave.net": (429, b""),
                    "https://ario.zigza.xyz": (0, b""),
                    "https://turbo-gateway.com": (503, b""),
                }
            )
        )
        with self.assertRaises(FetchError) as caught:
            fetch_matching(TX, DIGEST, fetcher)
        self.assertEqual(caught.exception.kind, "unavailable")

    def test_wrong_body_is_a_mismatch(self):
        fetcher = FakeFetcher(
            routes_for(
                {
                    "https://ar-io.dev": (200, b"other-bytes"),
                    "https://arweave.net": (429, b""),
                    "https://ario.zigza.xyz": (404, b""),
                    "https://turbo-gateway.com": (404, b""),
                }
            )
        )
        with self.assertRaises(FetchError) as caught:
            fetch_matching(TX, DIGEST, fetcher)
        self.assertEqual(caught.exception.kind, "mismatch")

    def test_connection_refused_does_not_raise(self):
        status, _headers, body = Fetcher().get("http://127.0.0.1:1/", timeout=2)
        self.assertEqual(status, 0)
        self.assertEqual(body, b"")

    def test_download_window_reaches_unlock_plus_two_hours(self):
        unlock = 1_792_314_000
        self.assertGreaterEqual(download_deadline(unlock + 5, unlock), unlock + 2 * 3600)
        self.assertGreaterEqual(download_deadline(1_000, unlock), unlock + 2 * 3600)

    def test_beacon_binding_accepts_sha256_of_signature(self):
        signature = bytes.fromhex("aabbcc")
        digest = hashlib.sha256(signature).hexdigest()
        self.assertIsNone(beacon_binding_error({"signature": signature.hex(), "randomness": digest}))
        self.assertIsNotNone(beacon_binding_error({"signature": signature.hex(), "randomness": "00" * 32}))

    def test_unobserved_inclusion_is_not_invalid(self):
        self.assertIsNone(committed_valid("UNKNOWN", "UNKNOWN"))
        self.assertIsNone(committed_valid("PASS", "UNKNOWN"))
        self.assertTrue(committed_valid("PASS", "PASS"))
        self.assertFalse(committed_valid("FAIL", "PASS"))

    def test_missing_tle_returns_127(self):
        import sealedbench.release as release

        old = release.TLE
        release.TLE = "/nonexistent/sealedbench-tle"
        try:
            code, _out, err = tle_decrypt(b"not-a-ciphertext")
        finally:
            release.TLE = old
        self.assertEqual(code, 127)
        self.assertIn("tle", err.lower())


if __name__ == "__main__":
    unittest.main()
