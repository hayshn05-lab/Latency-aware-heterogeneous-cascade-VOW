import tests
import json
from pathlib import Path
import tempfile
import unittest


class PipelineTests(unittest.TestCase):
    def test_offline_run_never_requires_token_and_writes_all_artifacts(self):
        from value_of_wait.pipeline import run_pilot

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            (cache / "tweets.json").write_text(json.dumps({"data": [{"id": "t", "created_at": "2026-05-20T10:00:00Z"}]}))
            (cache / "markets.json").write_text(json.dumps({"data": [{"id": "m", "question": "Elon Musk posts in window", "outcomes": [{"name": "YES", "token_id": "y"}, {"name": "NO", "token_id": "n"}]}]}))
            (cache / "trades_m.json").write_text(json.dumps({"data": [{"token_id": "y", "price": .4, "timestamp": "2026-05-20T09:59:59Z"}, {"token_id": "y", "price": .5, "timestamp": "2026-05-20T10:00:05Z"}, {"token_id": "y", "price": .6, "timestamp": "2026-05-20T10:30:00Z"}]}))
            config = {"handle": "elonmusk", "window_start": "2026-05-19T16:00:00Z", "window_end": "2026-05-26T16:00:00Z", "search_query": "Elon Musk post", "bundle_gap_seconds": 60, "horizons_seconds": [5, 1800], "staleness_seconds": 900, "terminal_move_floor": .005, "base_url": "https://lum.id/findata", "cache_dir": str(cache)}
            output = root / "output"
            run_pilot(config, output, offline=True, environment={})

            self.assertTrue((output / "summary.json").exists())
            self.assertIn("included", (output / "market_validation.csv").read_text())


if __name__ == "__main__":
    unittest.main()
