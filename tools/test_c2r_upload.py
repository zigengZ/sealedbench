import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import v2_upload_results as up


class UploadTests(unittest.TestCase):
    def test_dry_never_invokes_uploader_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'results/batches/b2r';dest.mkdir(parents=True)
            up.write_json(dest/'txids.json',{'items':{}})
            up.write_json(root/'results/batches/p2r_upload_ledger.json',{'uploads':[],'count':5,'total_bytes':135875})
            (dest/'scores.json').write_bytes(b'{}')
            item={'batch':'b2r','type':'results','path':'results/batches/b2r/scores.json'}
            with patch.object(up.subprocess,'run',side_effect=AssertionError('wallet path invoked')):
                up.upload(root,[item],True)
                first=(dest/'txids.json').read_bytes()
                up.upload(root,[item],True)
                self.assertEqual(first,(dest/'txids.json').read_bytes())
            ledger=json.loads((root/'results/batches/v2_dry_upload_ledger.json').read_text())
            self.assertEqual(ledger['count'],6)
            self.assertTrue(json.loads(first)['items']['results']['dry_run'])

    def test_caps_are_checked_before_any_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'results/batches/b2';dest.mkdir(parents=True)
            up.write_json(dest/'txids.json',{'items':{}})
            up.write_json(root/'results/batches/p2r_upload_ledger.json',{'uploads':[],'count':25,'total_bytes':135875})
            path=dest/'scores.json';path.write_bytes(b'{}')
            item={'batch':'b2','type':'results','path':str(path.relative_to(root))}
            with self.assertRaises(RuntimeError):up.plan_budget(root,[item],False)
            path.write_bytes(b'x'*(100*1024+1))
            with self.assertRaisesRegex(RuntimeError,'100 KiB'):up.plan_budget(root,[item],False)

    def test_archive_includes_exam_and_reference_evidence(self):
        import io, tarfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for kind in ('runs','reference_runs'):
                path=root/'results/batches/b2r'/kind/'model'
                path.mkdir(parents=True)
                (path/'item.txt').write_text('answer')
                (path/'item.json').write_text('{}')
                (path/'item.stderr').write_text('timings')
            blob=up.pack(root,'b2r','model')
            with tarfile.open(fileobj=io.BytesIO(blob),mode='r:gz') as tar:
                names=tar.getnames()
            self.assertEqual(len(names),6)
            self.assertIn('reference_runs/model/item.txt',names)
            self.assertIn('runs/model/item.stderr',names)

    def test_real_mode_invokes_existing_uploader(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);dest=root/'results/batches/b2';dest.mkdir(parents=True)
            up.write_json(dest/'txids.json',{'items':{}})
            up.write_json(root/'results/batches/p2r_upload_ledger.json',{'uploads':[],'count':5,'total_bytes':135875})
            (dest/'scores.json').write_bytes(b'{}')
            item={'batch':'b2','type':'results','path':'results/batches/b2/scores.json'}
            with patch.object(up.subprocess,'run') as run:
                up.upload(root,[item],False)
                self.assertEqual(run.call_args.args[0][0],'node')
                self.assertTrue(run.call_args.kwargs['check'])

if __name__=='__main__':unittest.main()
