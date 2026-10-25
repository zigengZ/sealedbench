#!/usr/bin/env python3
"""Replay must not treat an existing output directory as a fresh run."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

import sealedbench.replay as replay


class ReplayHotfixTests(unittest.TestCase):
    def test_replay_allocates_a_fresh_directory(self):
        source = inspect.getsource(replay.replay)
        self.assertIn("fresh_replay_dir(", source)
        self.assertNotIn('batch_dir(batch) / "replay" / model', source)

    def test_fresh_directory_ignores_stale_completions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = replay.batch_dir
            replay.batch_dir = lambda batch: root / batch
            try:
                legacy = root / "b1" / "replay" / "demo-model"
                legacy.mkdir(parents=True)
                (legacy / "arith_word-0000.txt").write_bytes(b"STALE")
                (legacy / "arith_word-0000.json").write_text('{"returncode": 0}\n')
                first = replay.fresh_replay_dir("b1", "demo-model")
                (first / "arith_word-0000.txt").write_bytes(b"FIRST")
                second = replay.fresh_replay_dir("b1", "demo-model")
                self.assertNotEqual(first, legacy)
                self.assertNotEqual(first, second)
                self.assertEqual((first / "arith_word-0000.txt").read_bytes(), b"FIRST")
                self.assertFalse((second / "arith_word-0000.txt").exists())
                self.assertEqual((legacy / "arith_word-0000.txt").read_bytes(), b"STALE")
            finally:
                replay.batch_dir = original


if __name__ == "__main__":
    unittest.main()
