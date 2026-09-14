import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

class PhaseOneDataTests(unittest.TestCase):
    def test_receipt_uses_declared_feed_delay_not_warehouse_ingest(self):
        from value_of_wait.phase1_data import clean_tweet
        row = {"tweet_id": "123", "created_at": "2026-09-06T00:00:00Z", "ingest_ts": "2026-09-07T12:00:00Z", "text": "A new event", "author_username": "reporter", "lang": "en", "tweet_type": "original"}
        clean, reason = clean_tweet(row, feed_delay_seconds=5)
        self.assertIsNone(reason)
        self.assertEqual(clean["receipt_ts"], 1788652805.0)
        self.assertEqual(clean["receipt_basis"], "source_plus_simulated_feed_delay")
        row["tweet_type"] = "reply"
        self.assertEqual(clean_tweet(row, feed_delay_seconds=5)[1], "unsupported_context")

    def test_book_keeps_side_specific_liquidity_and_rejects_crossed_state(self):
        from value_of_wait.phase1_data import clean_book
        row = {"asset_id": "101", "snapshot_ts": "2026-09-06T00:05:00Z", "source": "polymarket", "bids": [], "asks": [[0.4, 20]], "min_order_size": 5}
        book = clean_book(row)
        self.assertEqual(book["quality"], "ask_only")
        self.assertTrue(book["can_buy"])
        self.assertFalse(book["can_sell"])
        row["bids"] = [[0.5, 10]]
        self.assertEqual(clean_book(row)["quality"], "crossed")
        self.assertFalse(clean_book(row)["can_buy"])

    def test_build_creates_versioned_tables_without_promoting_conditional_metadata(self):
        import json
        import sqlite3
        import tempfile
        from value_of_wait.research_db import ResearchDatabase
        from value_of_wait.phase1_build import build_phase1
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = ResearchDatabase(root / "research.sqlite")
            cid = "0x" + "a" * 64
            market = {"id": "m", "condition_id": cid, "question": "Will the event happen?", "outcomes": ["Yes", "No"], "clob_token_ids": ["101", "102"], "events": [{"id": "family1"}], "market_created_at": "2026-09-05T00:00:00Z", "start_date": "2026-09-05T00:00:00Z", "end_date": "2026-09-14T00:00:00Z"}
            db.ingest("markets", [market], "marketquery")
            db.ingest("tweets", [{"tweet_id": "123", "created_at": "2026-09-06T00:00:00Z", "text": "event news", "author_username": "reporter", "lang": "en", "tweet_type": "original"}], "tweetquery")
            books = [{"asset_id": "101", "snapshot_ts": "2026-09-06T" + time + "Z", "source": "polymarket", "bids": [[0.3, 20]], "asks": [[0.4, 20]], "min_order_size": 5} for time in ["00:05:00", "00:35:00"]]
            db.ingest("books", books, "bookquery")
            db.close()
            config = {"version": "phase1.v1", "database": str(root / "research.sqlite"), "release": str(root / "release"), "window": {"start": "2026-09-06T00:00:00Z", "end_exclusive": "2026-09-13T00:00:00Z"}, "feed_delay_seconds": 5, "sources": ["polymarket"], "exit_horizons_seconds": [1800], "max_wait_seconds": 900, "quantity": 10}
            result = build_phase1(config)
            self.assertEqual(result["counts"]["tweets"], 1)
            self.assertEqual(result["counts"]["markets"], 1)
            self.assertEqual(result["counts"]["strict_eligibility"], 0)
            self.assertEqual(result["counts"]["replay_intervals"], 1)
            before = (root / "release" / "data_manifest.json").read_bytes()
            self.assertEqual(build_phase1(config)["release_id"], result["release_id"])
            self.assertEqual((root / "release" / "data_manifest.json").read_bytes(), before)
            c = sqlite3.connect(root / "research.sqlite")
            self.assertEqual(c.execute("SELECT count(*) FROM records").fetchone()[0], 4)
            self.assertEqual(c.execute("SELECT count(*) FROM p1_strict_markets").fetchone()[0], 0)
            c.execute("UPDATE p1_tweets SET payload='{}'")
            c.commit()
            c.close()
            with self.assertRaisesRegex(ValueError, "fingerprint"):
                build_phase1(config)

    def test_structural_interval_requires_lifecycle_and_both_order_minima(self):
        from value_of_wait.phase1_data import eligible_interval
        market = {"created_ts": 0, "start_ts": 0, "end_ts": 190, "closed_ts": None}
        entry = {"ts": 100, "can_buy": True, "asks": [[0.4, 20]], "min_order_size": 5}
        exit_book = {"ts": 200, "can_sell": True, "bids": [[0.5, 20]], "min_order_size": 5}
        self.assertFalse(eligible_interval(market, entry, exit_book, 10))
        market["end_ts"] = 300
        exit_book["min_order_size"] = 15
        self.assertFalse(eligible_interval(market, entry, exit_book, 10))
        exit_book["min_order_size"] = 5
        self.assertTrue(eligible_interval(market, entry, exit_book, 10))

if __name__ == "__main__":
    unittest.main()
