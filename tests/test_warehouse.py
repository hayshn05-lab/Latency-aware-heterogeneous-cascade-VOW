"""Behavioral tests for SQL materialization and offline replay."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from value_of_wait.warehouse import WarehouseClient

class WarehouseTests(unittest.TestCase):
    def test_materialized_rows_are_cached_and_replayed_without_credentials(self):
        calls = []
        def transport(url, body, headers):
            calls.append(url)
            if body is not None:
                return json.dumps({'materialized_uri':'/blobs/retrievals/test/result.jsonl','rowcount':2}).encode()
            return b'{"id":"a"}\n{"id":"b"}\n'
        with tempfile.TemporaryDirectory() as tmp:
            client = WarehouseClient(Path(tmp), token='private-fixture', transport=transport)
            self.assertEqual(client.query('SELECT id FROM fixture'), [{'id':'a'},{'id':'b'}])
            self.assertEqual(len(calls), 2)
            offline = WarehouseClient(Path(tmp), offline=True)
            self.assertEqual(offline.query('SELECT id FROM fixture'), [{'id':'a'},{'id':'b'}])
            for p in Path(tmp).glob('*'):
                self.assertNotIn('private-fixture', p.read_text())
            record = client.records[0]
            self.assertEqual(record['rows'], 2)
            self.assertEqual(record['endpoint'], '/retrieve')
            self.assertTrue(record['retrieved_at'])

    def test_rejects_untrusted_materialization_path_before_authenticated_fetch(self):
        calls = []
        def transport(url, body, headers):
            calls.append(url)
            return json.dumps({'materialized_uri':'/../../outside','rowcount':0}).encode()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Unsafe materialization'):
                WarehouseClient(Path(tmp), token='private-fixture', transport=transport).query('SELECT 1')
            self.assertEqual(len(calls), 1)

    def test_network_exception_does_not_expose_credential_in_traceback(self):
        import traceback
        def transport(url,body,headers):raise OSError('Authorization: Bearer private-fixture')
        with tempfile.TemporaryDirectory() as tmp:
            try:WarehouseClient(Path(tmp),token='private-fixture',transport=transport).query('SELECT 1')
            except RuntimeError:
                text=traceback.format_exc()
                self.assertNotIn('Bearer private-fixture',text)
                self.assertNotIn('During handling',text)
            else:self.fail('Expected sanitized failure')

if __name__ == '__main__': unittest.main()
