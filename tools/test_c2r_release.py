import os
import unittest
from unittest.mock import patch

from sealedbench.release import fetch_matching
from sealedbench.v2.transport import gateways, retry


class ReleaseTests(unittest.TestCase):
    def test_retry_transient_gateway_and_beacon(self):
        for label in ('ciphertext', 'beacon', 'decrypt'):
            with patch('sealedbench.v2.transport.time.sleep') as sleep:
                operation = unittest.mock.Mock(side_effect=[RuntimeError('HTTP 503'), OSError('timeout'), 'ok'])
                self.assertEqual(retry(label, operation), 'ok')
                self.assertEqual(sleep.call_count, 2)

    def test_retry_exhaustion_is_failure(self):
        with patch('sealedbench.v2.transport.time.sleep'):
            with self.assertRaises(RuntimeError):
                retry('beacon', unittest.mock.Mock(side_effect=RuntimeError('offline')), attempts=2)

    def test_gateway_override_is_dry_only(self):
        with patch.dict(os.environ, {'SEALEDBENCH_V2_GATEWAYS': 'http://127.0.0.1:1', 'SEALEDBENCH_DRY_UPLOAD': '0'}):
            with self.assertRaises(ValueError):
                gateways()
        with patch.dict(os.environ, {'SEALEDBENCH_V2_GATEWAYS': 'http://127.0.0.1:1', 'SEALEDBENCH_DRY_UPLOAD': '1'}):
            self.assertEqual(gateways(), ('http://127.0.0.1:1',))

    def test_v2_does_not_query_author_or_arweave(self):
        import hashlib
        fetcher = unittest.mock.Mock()
        fetcher.get.return_value = (200, {}, b'cipher')
        fetch_matching('test', hashlib.sha256(b'cipher').hexdigest(), fetcher, gateways=('https://ar-io.dev', 'https://turbo-gateway.com'))
        self.assertEqual([c.args[0] for c in fetcher.get.call_args_list], ['https://ar-io.dev/test', 'https://turbo-gateway.com/test'])

    def test_hung_decrypt_returns_retryable_failure(self):
        import subprocess
        from sealedbench.release import tle_decrypt
        with patch('sealedbench.release.subprocess.run',side_effect=subprocess.TimeoutExpired('tle',180)):
            code,plain,error=tle_decrypt(b'cipher')
            self.assertEqual(code,124)
            self.assertIn('timed out',error)


if __name__ == '__main__':
    unittest.main()
