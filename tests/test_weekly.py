"""Bounded SQL export must not silently truncate a weekly dataset."""
import sys
import unittest
import tempfile
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from value_of_wait.weekly import export_pages, run
from value_of_wait.warehouse import WarehouseClient

class ExportTests(unittest.TestCase):
    def test_full_page_requires_another_page_and_reconciles_source_count(self):
        class Client:
            records=[]
            def query(self,sql):
                if 'count(*)' in sql:return [{'n':3}]
                if 'OFFSET 0' in sql:return [{'id':'a'},{'id':'b'}]
                if 'OFFSET 2' in sql:return [{'id':'c'}]
                raise AssertionError(sql)
        pages=[]
        n=export_pages(Client(), 'SELECT id FROM fixture', 'id', 2, lambda rows,sql:pages.extend(rows))
        self.assertEqual(n,3)
        self.assertEqual(pages,[{'id':'a'},{'id':'b'},{'id':'c'}])

    def test_supplementary_source_audit_replays_from_configured_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def transport(url,body,headers):
                return json.dumps({'materialized_uri':'/blobs/retrievals/test/result.jsonl','rowcount':1}).encode() if body else b'{"source":"fixture","rows":7}\n'
            WarehouseClient(root/'raw',token='private-fixture-token',transport=transport).query('SELECT source, rows FROM fixture')
            config={'dataset_version':'test','window':{},'cache':str(root/'raw'),'database':str(root/'db.sqlite'),'release':str(root/'release'),'page_size':5,'datasets':[], 'supplementary_queries':[{'name':'source_contract','sql':'SELECT source, rows FROM fixture'}]}
            result=run(config,offline=True)
            self.assertEqual(result['supplementary']['source_contract'],[{'source':'fixture','rows':7}])
            self.assertEqual(result['requests'][0]['rows'],1)

if __name__=='__main__':unittest.main()
