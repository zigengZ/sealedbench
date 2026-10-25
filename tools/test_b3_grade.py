"""b3 grader tests, including the real b2r rehearsal stdout files."""

import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sealedbench.v2.grade import (
    HASH_LINE_RE,
    canon_number,
    extract_last_fence,
    extract_strict_integer,
    grade_answer as grade_registered,
    is_truncated,
)
from sealedbench.v2.grade_b3 import (
    NORMALIZATION_SPEC,
    SENTINEL,
    grade_answer,
    normalize_stdout_bytes,
)
from sealedbench.v2.manifest_doc import LLAMA_BINARY, build_b3_manifest
from sealedbench.v2.constants import B2_CIPHERTEXT_SHA256, B3_BATCHES, CAP2_CIPHERTEXT_SHA256
from sealedbench.v2.scoring import calculate_scores
from sealedbench.v2.tarball import grader_sha256

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tools/fixtures/b3_b2r_stdout"
LIVE = Path("/root/codes/sealedbench-b2r/results/batches/b2r")
INTEGER_LINE = re.compile(r"^####[ \t]+(-?\d[\d,]*)[ \t]*(?:\[end of text\])?[ \t]*$")


class NormalizeTests(unittest.TestCase):
    def test_sentinel_is_13_bytes_and_removed_once(self):
        self.assertEqual(len(SENTINEL), 13)
        raw = b"#### 261 [end of text]\n"
        self.assertEqual(normalize_stdout_bytes(raw), b"#### 261")
        twice = b"#### 261 [end of text] [end of text]"
        self.assertEqual(normalize_stdout_bytes(twice), b"#### 261 [end of text]")
        self.assertIsNone(extract_strict_integer(normalize_stdout_bytes(twice).decode()))

    def test_same_line_sentinel_parses_and_registered_grader_does_not(self):
        raw = "#### 261 [end of text]\n"
        self.assertFalse(is_truncated(raw, 105, 768))
        registered = grade_registered("arith_word", "261", raw)
        self.assertTrue(registered.invalid)
        self.assertFalse(registered.correct)
        graded = grade_answer("arith_word", "261", raw.encode())
        self.assertEqual(graded.parsed, "261")
        self.assertTrue(graded.correct)
        self.assertFalse(graded.invalid)
        self.assertFalse(graded.truncated)

    def test_truncation_flag_still_wins(self):
        graded = grade_answer("graph_path", "9", b"#### 9 [end of text]\n", truncated=True)
        self.assertTrue(graded.truncated)
        self.assertTrue(graded.invalid)
        self.assertEqual(graded.parsed, "9")

    def test_code_fence_survives_the_suffix(self):
        raw = "```\n1\n```\n[end of text]\n"
        self.assertEqual(extract_last_fence(normalize_stdout_bytes(raw.encode()).decode()), "1\n")
        graded = grade_answer("code_output", "1", raw.encode())
        self.assertTrue(graded.correct)


class RealB2RTests(unittest.TestCase):
    def test_every_integer_line_in_the_rehearsal_parses(self):
        files = sorted(FIXTURES.rglob("*.txt"))
        self.assertGreaterEqual(len(files), 32)
        integer_files = 0
        rescued = 0
        for path in files:
            raw = path.read_bytes()
            live = LIVE / path.relative_to(FIXTURES)
            try:
                live_present = live.is_file()
            except PermissionError:  # the rehearsal checkout lives under /root on the development host
                live_present = False
            if live_present:
                self.assertEqual(raw, live.read_bytes(), str(path))
            text = raw.decode("utf-8")
            normalized = normalize_stdout_bytes(raw).decode("utf-8")
            matches = [canon_number(match.group(1)) for line in text.splitlines() if (match := INTEGER_LINE.match(line))]
            if matches:
                integer_files += 1
                parsed = extract_strict_integer(normalized)
                self.assertEqual(parsed, matches[-1], path)
                if extract_strict_integer(text) is None:
                    rescued += 1
            if HASH_LINE_RE.search(normalized):
                self.assertIsNotNone(extract_strict_integer(normalized), path)
            if "code_output" in path.parts:
                before = extract_last_fence(text)
                if before is not None:
                    self.assertEqual(extract_last_fence(normalized), before, path)
        self.assertGreaterEqual(integer_files, 8)
        self.assertGreaterEqual(rescued, 1)

    def test_registered_grader_hash_is_unchanged(self):
        for batch in ("b2", "cap2"):
            manifest = json.loads((ROOT / "results/batches" / batch / "manifest.json").read_text())
            self.assertEqual(grader_sha256(ROOT), manifest["grader"]["sha256"])
            self.assertEqual(manifest["grader"]["files"], ["sealedbench/v2/grade.py"])


class PostHocTests(unittest.TestCase):
    def test_primary_stays_invalid_and_posthoc_parses_the_same_line(self):
        manifest = json.loads((ROOT / "results/batches/b2/manifest.json").read_text())
        manifest["models"] = manifest["models"][:1]
        manifest["generator"]["families"] = [
            {"name": "arith_word", "n": 1},
            {"name": "code_output", "n": 0},
            {"name": "graph_path", "n": 0},
        ]
        manifest["reference"]["n"] = 1
        model = manifest["models"][0]["id"]
        items = [{
            "item_id": "arith_word-0000",
            "family": "arith_word",
            "oracle_answer": "261",
            "params": {"template_id": "test"},
        }]
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            runs = dest / "runs" / model
            ref = dest / "reference_runs" / model
            runs.mkdir(parents=True)
            ref.mkdir(parents=True)
            (dest / "items.jsonl").write_text(json.dumps(items[0]) + "\n")
            for directory, name, body in (
                (runs, "arith_word-0000", "#### 261 [end of text]\n"),
                (ref, "gsm8k-0000", "#### 18 [end of text]\n"),
            ):
                (directory / f"{name}.txt").write_text(body)
                (directory / f"{name}.stderr").write_text("eval time = 10.0 ms / 105 runs\n")
                (directory / f"{name}.json").write_text(json.dumps({"returncode": 0}))
            with patch("sealedbench.v2.scoring.batch_dir", return_value=dest), \
                 patch("sealedbench.v2.scoring.load_manifest", return_value=manifest), \
                 patch("sealedbench.v2.scoring._v2_reference", return_value=[{"item_id": "gsm8k-0000", "oracle_answer": "18"}]):
                scores = calculate_scores("b2")
            primary = scores["models"][model]
            self.assertEqual(primary["families"]["arith_word"]["correct"], 0)
            self.assertEqual(primary["families"]["arith_word"]["invalid"], 1)
            self.assertEqual(primary["gsm8k"]["correct"], 0)
            post = scores["posthoc_sentinel_normalization"]
            self.assertEqual(post["label"], "POST-HOC")
            self.assertFalse(post["registered_primary"])
            self.assertEqual(post["models"][model]["families"]["arith_word"]["correct"], 1)
            self.assertEqual(post["models"][model]["families"]["arith_word"]["invalid"], 0)
            self.assertEqual(post["models"][model]["gsm8k"]["correct"], 1)
            self.assertNotIn("posthoc_sentinel_normalization", primary)


class ManifestTests(unittest.TestCase):
    def test_b3_manifest_states_the_normalization_and_the_sealed_hashes(self):
        spec = B3_BATCHES["b3"]
        try:
            Path(LLAMA_BINARY).is_file()
        except PermissionError:
            self.skipTest("the frozen llama.cpp binary path is under /root and not readable here")
        doc = build_b3_manifest(
            ROOT,
            batch_id="b3",
            release_round=spec["release_round"],
            unlock_unix=spec["unlock_unix"],
            unlock_utc=spec["unlock_utc"],
            ciphertext_txid="pending",
            ciphertext_sha256="ab" * 32,
            ciphertext_bytes=10,
            plaintext_sha256="cd" * 32,
            plaintext_bytes=10,
            reference_txid="pending-ref",
            reference_sha256="ef" * 32,
            reference_bytes=10,
            vectors=[],
        )
        self.assertEqual(doc["grader"]["input_normalization"], NORMALIZATION_SPEC)
        self.assertIn("sealedbench/v2/grade_b3.py", doc["grader"]["files"])
        self.assertIn("sealedbench/v2/grade.py", doc["grader"]["files"])
        declared = {row["batch_id"]: row["ciphertext_sha256"] for row in doc["corrects"]["declared"]}
        self.assertEqual(declared["b2"], B2_CIPHERTEXT_SHA256)
        self.assertEqual(declared["cap2"], CAP2_CIPHERTEXT_SHA256)
        self.assertIn("before b1 unlocked", doc["corrects"]["statement"])
        self.assertEqual(doc["runtime"]["n_predict"]["graph_path"], 768)
        self.assertEqual(doc["runtime"]["n_predict"]["code_output"], 512)
        self.assertEqual(doc["release_round"], 33202612)
        self.assertEqual(grader_sha256(ROOT, doc["grader"]["files"]), doc["grader"]["sha256"])
        self.assertNotEqual(doc["grader"]["sha256"], grader_sha256(ROOT))


if __name__ == "__main__":
    unittest.main()
