import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from sealedbench.v2.verification import verify, inclusion, result


class FakeNetwork:
    def __init__(self, stamp=1500, code=200, member=True):
        self.stamp,self.code,self.member=stamp,code,member
    def json(self,url):
        if 'upload.ardrive.io' in url:return self.code,{'bundleId':'bundle','startOffsetInRootBundle':10,'payloadDataStart':5,'payloadContentLength':3}
        if '/tx/' in url:return self.code,{'block_height':42,'block_indep_hash':'block'}
        return self.code,{'height':42,'indep_hash':'block','timestamp':self.stamp,'txs':['bundle'] if self.member else []}
    def get(self,url,headers=None):return self.code,b'abc',{}


class VerifyTests(unittest.TestCase):
    def setUp(self):
        proof=patch('sealedbench.v2.verification.locate_payload',return_value={'start':10,'payload_start':5,'payload_len':3,'url':'https://gateway/bundle'})
        payload=patch('sealedbench.v2.verification.fetch_range',return_value=b'abc')
        proof.start();payload.start();self.addCleanup(proof.stop);self.addCleanup(payload.stop)

    def test_exit_semantics(self):
        for rows,want in [([('PASS','','')],('PASS',0)),([('WEAK','','')],('WEAK',2)),([('UNKNOWN','','')],('UNKNOWN',2)),([('FAIL','',''),('UNKNOWN','','')],('FAIL',1))]:
            self.assertEqual(result(rows),want)

    def test_own_deadline_and_margin(self):
        for stamp,want in [(1399,True),(1400,True),(1401,False)]:
            rows=[]
            self.assertEqual(inclusion(FakeNetwork(stamp),'tx',hashlib.sha256(b'abc').hexdigest(),2000,'batch',rows),want)
            self.assertEqual(any(r[0]=='FAIL' for r in rows),not want)

    def test_network_or_missing_membership_is_unknown(self):
        for network in (FakeNetwork(code=429),FakeNetwork(code=503),FakeNetwork(member=False)):
            rows=[]
            self.assertIsNone(inclusion(network,'tx','hash',2000,'batch',rows))
            self.assertEqual(result(rows),('UNKNOWN',2))

    def test_fake_txids_and_beacon_outage_do_not_crash(self):
        root=Path.cwd()
        manifest=json.loads((root/'results/batches/b2/manifest.json').read_text())
        tx=json.loads((root/'results/batches/b2/txids.json').read_text());tx['dry_run']=True
        class Offline:
            def json(self,url):return 503,None
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'results/batches/b2r';dest.mkdir(parents=True)
            (dest/'manifest.json').write_text(json.dumps(manifest));(dest/'txids.json').write_text(json.dumps(tx))
            (dest/'reference.json').write_bytes((root/'results/batches/b2/reference.json').read_bytes())
            with patch.dict(os.environ,{'SEALEDBENCH_ROOT':tmp}),patch('sealedbench.v2.verification.grader_sha256',return_value=manifest['grader']['sha256']):
                self.assertEqual(verify('b2r',Offline()),2)
            self.assertNotIn('FAIL',(dest/'verify_seal.txt').read_text())

    def test_existing_verify_seal_is_not_replaced(self):
        root=Path.cwd()
        manifest=json.loads((root/'results/batches/b2/manifest.json').read_text())
        tx=json.loads((root/'results/batches/b2/txids.json').read_text());tx['dry_run']=True
        class Offline:
            def json(self,url):return 503,None
        registered='RESULT UNKNOWN\n'
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'results/batches/b2r';dest.mkdir(parents=True)
            (dest/'manifest.json').write_text(json.dumps(manifest));(dest/'txids.json').write_text(json.dumps(tx))
            (dest/'reference.json').write_bytes((root/'results/batches/b2/reference.json').read_bytes())
            (dest/'verify_seal.txt').write_text(registered)
            buf=io.StringIO()
            with patch.dict(os.environ,{'SEALEDBENCH_ROOT':tmp}),patch('sealedbench.v2.verification.grader_sha256',return_value=manifest['grader']['sha256']),redirect_stdout(buf):
                self.assertEqual(verify('b2r',Offline()),2)
            self.assertEqual((dest/'verify_seal.txt').read_text(),registered)
            self.assertTrue(buf.getvalue().endswith('RESULT UNKNOWN\n'))
            self.assertNotEqual(buf.getvalue(),registered)

if __name__=='__main__':unittest.main()
