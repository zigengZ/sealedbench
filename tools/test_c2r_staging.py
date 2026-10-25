import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import v2_stage_results as stage


class StagingTests(unittest.TestCase):
    def test_stages_named_artifacts_not_scratch_sources_or_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'results/batches/b2r';dest.mkdir(parents=True)
            (dest/'manifest.json').write_text(json.dumps({'models':[]}))
            (dest/'scratch.txt').write_text('scratch')
            (dest/'src').mkdir();(dest/'src/secret.bin').write_bytes(b'not an artifact')
            (dest/'generator.tar.gz').write_bytes(b'plaintext')
            artifact=dest/'scores.json';artifact.write_text('{}')
            with patch.object(stage,'ROOT',root),patch.object(stage,'artifacts',return_value=[artifact]):
                selected=stage.paths('b2r')
            self.assertIn('results/batches/b2r/scores.json',selected)
            self.assertIn('results/batches/b2r/manifest.json',selected)
            for bad in ('scratch.txt','src/secret.bin','generator.tar.gz'):
                self.assertNotIn('results/batches/b2r/'+bad,selected)
            self.assertFalse(any(p.startswith(('sealedbench/','tools/','review/')) for p in selected))

if __name__=='__main__':unittest.main()
