"""Document the frozen EOS/strict-integer incompatibility without changing it."""
import json
from pathlib import Path
import unittest
from sealedbench.v2.grade import grade_answer, is_truncated
from sealedbench.v2.tarball import grader_sha256

class SealedPolicyTests(unittest.TestCase):
    def test_observed_same_line_eos_remains_invalid_under_the_seal(self):
        raw='#### 261 [end of text]\n'
        self.assertFalse(is_truncated(raw,105,768))
        grade=grade_answer('arith_word','261',raw)
        self.assertTrue(grade.invalid)
        self.assertFalse(grade.correct)

    def test_grader_still_matches_both_immutable_manifests(self):
        for batch in ('b2','cap2'):
            manifest=json.loads(Path(f'results/batches/{batch}/manifest.json').read_text())
            self.assertEqual(grader_sha256(Path.cwd()),manifest['grader']['sha256'])

if __name__=='__main__':unittest.main()
