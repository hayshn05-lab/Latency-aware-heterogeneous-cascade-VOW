import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.starter_dataset import build_starter_dataset


CONDITION = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


class FakeFindataClient:
    def get_json(self, endpoint, params=None):
        params = params or {}
        if endpoint.startswith("/catalog/tables/"):
            return {"table": endpoint.split("/")[-1], "schema_verified": True}
        if endpoint == "/prediction-markets/markets/search":
            return [{
                "condition_id": CONDITION,
                "market_id": CONDITION,
                "title": "Will Bitcoin reach the threshold?",
                "slug": "will-bitcoin-reach-100k",
                "volume": 1000,
                "start_date": "2026-05-01T00:00:00Z",
                "end_date": "2026-06-01T00:00:00Z",
                "closed": True,
            }]
        if endpoint == f"/prediction-markets/markets/polymarket/{CONDITION}":
            return {
                "condition_id": CONDITION,
                "market_id": "42",
                "question": "Will Bitcoin reach the threshold?",
                "slug": "will-bitcoin-reach-100k",
                "outcomes": ["Yes", "No"],
                "outcome_prices": ["1", "0"],
                "clob_token_ids": ["111", "222"],
                "start_date": "2026-05-01T00:00:00Z",
                "end_date": "2026-06-01T00:00:00Z",
                "closed": True,
            }
        if endpoint == "/kols/tweets/search":
            return [{
                "tweet_id": "9001",
                "created_at": "2026-05-20T12:00:00Z",
                "kol_username": "source",
                "text": "Bitcoin event",
            }]
        if endpoint == f"/prediction-markets/trades/polymarket/{CONDITION}":
            return [
                {"trade_id": "t1", "token_id": "111", "ts": "2026-05-20T12:00:01Z", "price": 0.5, "size": 2, "side": "BUY"},
                {"trade_id": "t2", "token_id": "222", "ts": "2026-05-20T12:00:10Z", "price": 0.4, "size": 3, "side": "SELL"},
            ]
        if endpoint.startswith("/prediction-markets/orderbook/polymarket/"):
            asset = endpoint.rsplit("/", 1)[-1]
            return [
                {"asset_id": asset, "condition_id": CONDITION, "snapshot_ts": stamp, "bids": [["0.49", "10"]], "asks": [["0.51", "10"]]}
                for stamp in (
                    "2026-05-20T12:00:00Z",
                    "2026-05-20T12:00:05Z",
                    "2026-05-20T12:01:00Z",
                    "2026-05-20T12:30:00Z",
                )
            ]
        raise AssertionError((endpoint, params))


class DatasetBuilderTests(unittest.TestCase):
    def test_online_build_and_offline_reconstruction_match(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "dataset_version": "fixture-v1",
                "base_url": "https://fixture",
                "raw_dir": str(root / "raw"),
                "interim_dir": str(root / "interim"),
                "sample_start": "2026-05-01T00:00:00Z",
                "sample_end": "2026-06-01T00:00:00Z",
                "market_search_limit": 10,
                "markets_per_stratum": 1,
                "tweet_search_limit": 10,
                "events_per_market": 1,
                "rest_limit": 1000,
                "window_before_seconds": 60,
                "window_after_seconds": 1800,
                "required_book_offsets_seconds": [5, 60, 1800],
                "max_book_age_seconds": 1,
                "strata": [{"name": "crypto", "query": "bitcoin"}],
            }
            release_one, output_one = root / "release-one", root / "output-one"
            release_one.mkdir(parents=True)
            unrelated = release_one / "unrelated.txt"
            unrelated.write_text("not owned by the dataset builder\n", encoding="utf-8")
            summary = build_starter_dataset(config, release_one, output_one, offline=False, client=FakeFindataClient())
            self.assertEqual(summary["evidence_tier"], "H1")
            self.assertEqual(summary["strict_effective_family_count"], 0)
            self.assertEqual(summary["diagnostic_pairs_with_valid_books"], 1)
            manifest = json.loads((release_one / "data_manifest.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(manifest["source_requests"]), 9)
            self.assertNotIn("Authorization", json.dumps(manifest))
            self.assertNotIn(unrelated.name, {artifact["path"] for artifact in manifest["release_artifacts"]})
            with (release_one / "event_market_candidates.csv").open(encoding="utf-8", newline="") as handle:
                pair = next(csv.DictReader(handle))
            self.assertEqual(pair["pit_active_verified"], "False")
            self.assertEqual(pair["pit_reason"], "historical index timestamp unavailable")
            self.assertEqual(pair["valid_books"], "True")

            release_two, output_two = root / "release-two", root / "output-two"
            replay_summary = build_starter_dataset(config, release_two, output_two, offline=True)
            self.assertEqual(summary, replay_summary)
            unrelated.unlink()
            for first in sorted(path for path in release_one.iterdir() if path.is_file()):
                self.assertEqual(first.read_bytes(), (release_two / first.name).read_bytes(), first.name)
            for first in sorted(path for path in output_one.iterdir() if path.is_file()):
                self.assertEqual(first.read_bytes(), (output_two / first.name).read_bytes(), first.name)


if __name__ == "__main__":
    unittest.main()
