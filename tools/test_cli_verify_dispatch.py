"""CLI dispatch that must not touch the network."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path


class CliDispatchTests(unittest.TestCase):
    def test_v2_verify_rejects_a_txid_that_is_not_the_index(self) -> None:
        from sealedbench.cli import main

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = main(["verify", "--batch", "b3", "--txid", "not-the-index"])
        self.assertEqual(rc, 1)
        self.assertIn("does not match the published index", buf.getvalue())
        self.assertIn("vlVlUfyBn4IUmbXjkSX8079QuySP-Qqr8rN8TbivzTg", buf.getvalue())

    def test_entropy_and_reference_paths_follow_the_checkout(self) -> None:
        source = Path(__file__).resolve().parents[1].joinpath("sealedbench", "cli.py").read_text()
        self.assertNotIn("/root/codes/sealedbench", source)
