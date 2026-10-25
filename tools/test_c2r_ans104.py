import hashlib
import json
from pathlib import Path
import unittest
from sealedbench.v2.ans104 import (parse_header,parse_data_item_prefix,encode_id,count_from_prefix,locate_payload,BundleFormatError,BundleUnavailable)


def fixture():
    sig=b's'*512
    payload=b'payload'
    item=(1).to_bytes(2,'little')+sig+b'o'*512+b'\0\0'+(0).to_bytes(8,'little')*2+payload
    item_id=encode_id(hashlib.sha256(sig).digest())
    other=b'xx'
    header=(2).to_bytes(32,'little')+len(other).to_bytes(32,'little')+b'z'*32+len(item).to_bytes(32,'little')+hashlib.sha256(sig).digest()
    return header+other+item,item_id,len(header)+len(other),len(item)-len(payload)


class BundleTests(unittest.TestCase):
    def test_offsets_are_cumulative_sizes_before_current_item(self):
        blob,item_id,start,relative=fixture()
        entries=parse_header(blob[:160]);entry=entries[item_id]
        self.assertEqual(entry['start'],start)
        parsed=parse_data_item_prefix(blob[start:start+entry['size']],item_id,entry['size'])
        self.assertEqual(parsed['payload_start'],relative)
        self.assertEqual(blob[start+relative:],b'payload')

    def test_signature_hash_binds_id(self):
        blob,item_id,start,relative=fixture()
        with self.assertRaises(BundleFormatError):parse_data_item_prefix(blob[start:],'wrong',len(blob)-start)

    def test_short_and_unbounded_tables_are_rejected(self):
        with self.assertRaises(BundleFormatError):count_from_prefix(b'short')
        with self.assertRaises(BundleUnavailable):count_from_prefix((2**200).to_bytes(32,'little'))
        blob,*_=fixture()
        with self.assertRaises(BundleFormatError):parse_header(blob[:100])

    def test_range_path_needs_no_turbo_offsets(self):
        blob,item_id,start,relative=fixture()
        class Network:
            def get(self,url,headers):
                begin,end=map(int,headers['Range'].removeprefix('bytes=').split('-'))
                return 206,blob[begin:end+1],{'Content-Range':f'bytes {begin}-{end}/{len(blob)}'}
        proof=locate_payload(Network(),'https://gateway','bundle',item_id)
        self.assertEqual((proof['start'],proof['payload_start'],proof['payload_len']),(start,relative,7))

    def test_real_b2_bundle_range_fixture(self):
        from sealedbench.v2.ans104 import fetch_range
        fixture=Path(__file__).parent/'fixtures/c2r_ans104'
        routes={}
        for path in fixture.glob('*.json'):
            doc=json.loads(path.read_text())
            body=path.with_suffix('.bin').read_bytes()
            self.assertEqual(hashlib.sha256(body).hexdigest(),doc['sha256'])
            routes[(doc['url'],tuple(sorted(doc['request_headers'].items())))]=(doc['http'],body,doc['response_headers'])
        class RecordedGateway:
            def get(self,url,headers):return routes.get((url,tuple(sorted(headers.items()))),(404,b'',{}))
        gateway=RecordedGateway()
        proof=locate_payload(gateway,'https://ar-io.dev','VWHJrEUcS-d9EXMzzJr9k6Qr2WKQLR9iwiMfm4nglgo','kVO8I3b3xRDewqzkPDEKqBsIcdobkgs-bM_zOx974w8')
        self.assertEqual((proof['bundle_items'],proof['index'],proof['start'],proof['size']),(120,116,30596949,16860))
        self.assertEqual((proof['payload_start'],proof['payload_len']),(1397,15463))
        raw=fetch_range(gateway,proof['url'],proof['start']+proof['payload_start'],proof['payload_len'])
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'d304125d451a00933e073f47168319739d9367ffc23aafffc14ad3c1feea6a0c')

if __name__=='__main__':unittest.main()
