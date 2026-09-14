import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.universe_probe import probe_market_universe


CONDITION = "0xcccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"


class ProbeClient:
    def get_json(self, endpoint, params=None):
        if endpoint == "/prediction-markets/markets/search":
            return [{"condition_id": CONDITION, "title": "A market", "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-02-01T00:00:00Z"}]
        if "/trades/" in endpoint:
            return [{"trade_id": "t", "token_id": "111", "ts": "2026-01-15T00:00:00Z", "price": 0.5, "size": 1}]
        if "/orderbook/" in endpoint:
            asset = endpoint.rsplit("/", 1)[-1]
            return [{"asset_id": asset, "condition_id": CONDITION, "snapshot_ts": "2026-01-15T00:00:00.123Z", "bids": [["0.49", "1"]], "asks": [["0.51", "1"]]}]
        if endpoint.endswith(CONDITION):
            return {"condition_id": CONDITION, "market_id": "7", "question": "A market", "outcomes": ["Yes", "No"], "outcome_prices": ["1", "0"], "clob_token_ids": ["111", "222"], "start_date": "2026-01-01T00:00:00Z", "end_date": "2026-02-01T00:00:00Z", "closed": True}
        raise AssertionError(endpoint)


class UniverseProbeTests(unittest.TestCase):
    def test_probe_records_trade_and_both_asset_l2_coverage_and_replays_offline(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config = {
                "dataset_version": "probe-fixture",
                "base_url": "https://fixture",
                "universe_raw_dir": str(root / "raw"),
                "sample_start": "2026-01-01T00:00:00Z",
                "sample_end": "2026-02-01T00:00:00Z",
                "market_search_limit": 5,
                "strata": [{"name": "fixture", "query": "market", "status": "closed"}],
            }
            first = root / "first"
            summary = probe_market_universe(config, first, offline=False, client=ProbeClient())
            self.assertEqual(summary["markets_scanned"], 1)
            self.assertEqual(summary["markets_with_any_trade"], 1)
            self.assertEqual(summary["markets_with_both_asset_l2"], 1)
            manifest = json.loads((first / "universe_probe_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "market-universe-probe-v1")
            second = root / "second"
            self.assertEqual(summary, probe_market_universe(config, second, offline=True))
            for path in first.iterdir():
                self.assertEqual(path.read_bytes(), (second / path.name).read_bytes(), path.name)


if __name__ == "__main__":
    unittest.main()
