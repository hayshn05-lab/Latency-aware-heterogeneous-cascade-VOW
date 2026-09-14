"""Storage preserves versions and supports idempotent, incremental imports."""
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from value_of_wait.research_db import ResearchDatabase

class DatabaseTests(unittest.TestCase):
    def test_import_is_idempotent_but_retains_distinct_source_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=ResearchDatabase(Path(tmp)/'research.sqlite')
            rows=[{'tweet_id':'1','created_at':'2026-09-06T00:00:00Z','text':'original','ingest_ts':'2026-09-06T00:01:00Z'}]
            db.ingest('tweets',rows,'query-a')
            db.ingest('tweets',rows,'query-a')
            db.ingest('tweets',[dict(rows[0],text='revision')],'query-b')
            self.assertEqual(db.counts(),{'tweets':2})
            self.assertEqual(db.connection.execute('SELECT count(*) FROM record_sources').fetchone()[0],2)
            self.assertEqual(db.connection.execute("SELECT count(*) FROM records WHERE entity_id='1'").fetchone()[0],2)
            db.close()

    def test_source_times_are_normalized_for_correct_index_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=ResearchDatabase(Path(tmp)/'research.sqlite')
            db.ingest('trades',[
              {'trade_id':'later','ts':'2026-09-06T00:00:00.100Z'},
              {'trade_id':'earlier','ts':'2026-09-06T00:00:00Z'}], 'q')
            got=db.connection.execute('SELECT entity_id FROM records ORDER BY source_time').fetchall()
            db.close()
            self.assertEqual(got,[('earlier',),('later',)])

if __name__=='__main__':unittest.main()
