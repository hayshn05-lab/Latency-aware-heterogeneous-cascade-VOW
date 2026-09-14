"""Replay diagnostics distinguish source time from provider availability."""
import sys
import unittest
import tempfile
import json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from value_of_wait.weekly_audit import asof_status, audit_database, require_complete_release
from value_of_wait.research_db import ResearchDatabase

class AvailabilityTests(unittest.TestCase):
    def test_incomplete_acquisition_cannot_be_reported_as_coverage_absence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);config={'release':str(root),'datasets':[{'kind':'books','select_sql':'SELECT books'}]}
            (root/'data_manifest.json').write_text(json.dumps({'datasets':{}}))
            with self.assertRaisesRegex(ValueError,'incomplete'):
                require_complete_release(config)
            (root/'data_manifest.json').write_text(json.dumps({'datasets':{'books':{'complete':True,'selection':'SELECT other'}}}))
            with self.assertRaisesRegex(ValueError,'selection'):
                require_complete_release(config)

    def test_future_ingestion_is_not_available_and_invalid_latest_is_not_skipped(self):
        # tuples: source time, ingestion time, quality, content signature
        rows=[(10.0,11.0,'valid','a'),(12.0,20.0,'valid','b')]
        self.assertEqual(asof_status(rows,15.0,10.0,provider=True),('valid',5.0))
        self.assertEqual(asof_status(rows,15.0,10.0,provider=False),('valid',3.0))
        rows.append((14.0,14.0,'missing_side','c'))
        self.assertEqual(asof_status(rows,15.0,10.0,provider=True)[0],'invalid')
        self.assertEqual(asof_status(rows,9.0,10.0,provider=True)[0],'missing')
        self.assertEqual(asof_status(rows,50.0,10.0,provider=True)[0],'stale')

    def test_unknown_ingestion_and_same_timestamp_conflicts_fail_closed(self):
        self.assertEqual(asof_status([(10.0,None,'valid','a')],10.0,5,provider=True)[0],'missing')
        self.assertEqual(asof_status([(10.0,None,'valid','a')],10.0,5,provider=False)[0],'valid')
        rows=[(10.0,10.0,'valid','a'),(10.0,10.0,'valid','b')]
        self.assertEqual(asof_status(rows,10.0,5,provider=True)[0],'conflict')

    def test_conflicting_market_token_versions_are_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/'db.sqlite';db=ResearchDatabase(path)
            cid='0x'+'2'*64
            db.ingest('markets',[{'condition_id':cid,'outcomes':['Yes','No'],'clob_token_ids':tokens} for tokens in [['10','20'],['30','40']]],'q')
            db.ingest('markets',[{'condition_id':'0x'+'3'*64,'outcomes':['Yes','No'],'clob_token_ids':['30','50']}],'q')
            db.close()
            result=audit_database(path,root/'release',{'start':'2026-09-06T00:00:00Z','end_exclusive':'2026-09-13T00:00:00Z'}, {'offsets_seconds':[0],'max_age_seconds':5,'sample_events':10})
            self.assertEqual(result['mapped_yes_no_markets'],0)

    def test_valid_book_coverage_does_not_imply_semantic_or_execution_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); path=root/'db.sqlite'
            db=ResearchDatabase(path)
            cid='0x'+'1'*64
            db.ingest('markets',[{'id':'m','condition_id':cid,'outcomes':['Yes','No'],'clob_token_ids':['10','20'],'events':[{'id':'family'}],'ingest_ts':'2026-09-07T00:00:00Z'}],'q')
            db.ingest('tweets',[{'tweet_id':'p','created_at':'2026-09-06T00:00:05Z','ingest_ts':'2026-09-06T00:00:06Z'}],'q')
            db.ingest('books',[{'asset_id':a,'condition_id':None,'snapshot_ts':'2026-09-06T00:00:04Z','ingest_ts':'2026-09-06T00:00:04Z','bids':[['0.4','10']],'asks':[['0.6','10']]} for a in ['10','20']],'q')
            db.close()
            result=audit_database(path,root/'release',{'start':'2026-09-06T00:00:00Z','end_exclusive':'2026-09-13T00:00:00Z'}, {'offsets_seconds':[0], 'max_age_seconds':5,'sample_events':10})
            self.assertEqual(result['book_quality']['valid'],2)
            self.assertEqual(result['source_timestamp_precision']['classification']['tweets'],'seconds_only_observed')
            self.assertEqual(result['source_timestamp_precision']['classification']['trades'],'unknown')
            self.assertEqual(result['both_token_book_markets'],1)
            self.assertEqual(result['sampled_post_count'],1)
            self.assertEqual(result['tweet_text_nonempty'],0)
            self.assertEqual(result['distinct_tweet_ids'],1)
            self.assertEqual(result['strict_h2_semantic_pairs'],0)
            self.assertEqual(result['execution_ready'],False)
            self.assertEqual(result['structural_pairs_complete_provider'],1)

if __name__=='__main__':unittest.main()
