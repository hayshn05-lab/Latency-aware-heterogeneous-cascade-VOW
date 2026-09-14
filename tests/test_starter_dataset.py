from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.replay_audit import parse_l2_snapshot
from value_of_wait.starter_dataset import (
    deduplicate_full_rows,
    point_in_time_eligibility,
    summarize_snapshot_series,
)


class StarterDatasetContractTests(unittest.TestCase):
    def test_point_in_time_market_requires_index_and_historical_open_evidence(self):
        market = {
            "start_date": "2026-05-20T00:00:00Z",
            "end_date": "2026-05-21T00:00:00Z",
            "indexed_ts": "2026-05-19T23:00:00Z",
            "historical_open": True,
        }
        self.assertEqual(
            point_in_time_eligibility("2026-05-20T12:00:00Z", market),
            {"eligible": True, "reason": "verified active/open/indexed at event time"},
        )
        missing_index = dict(market)
        missing_index.pop("indexed_ts")
        self.assertEqual(
            point_in_time_eligibility("2026-05-20T12:00:00Z", missing_index),
            {"eligible": False, "reason": "historical index timestamp unavailable"},
        )
        not_open = dict(market, historical_open=False)
        self.assertEqual(
            point_in_time_eligibility("2026-05-20T12:00:00Z", not_open),
            {"eligible": False, "reason": "historical open state not verified"},
        )

    def test_full_row_deduplication_does_not_use_trade_id_alone(self):
        first = {"trade_id": "same", "asset_id": "111", "ts": "2026-05-20T12:00:00Z", "price": 0.4}
        second = {"trade_id": "same", "asset_id": "222", "ts": "2026-05-20T12:00:01Z", "price": 0.6}
        actual = deduplicate_full_rows([second, first, dict(first)])
        self.assertEqual(actual, [first, second])

    def test_snapshot_frequency_summary_uses_observed_gaps(self):
        rows = [
            parse_l2_snapshot({"asset_id": "111", "snapshot_ts": "2026-05-20T12:00:20Z", "bids": [["0.49", "1"]], "asks": [["0.51", "1"]]}),
            parse_l2_snapshot({"asset_id": "111", "snapshot_ts": "2026-05-20T12:00:00Z", "bids": [["0.48", "1"]], "asks": [["0.52", "1"]]}),
            parse_l2_snapshot({"asset_id": "111", "snapshot_ts": "2026-05-20T12:00:05Z", "bids": [["0.49", "1"]], "asks": [["0.51", "1"]]}),
        ]
        self.assertEqual(
            summarize_snapshot_series(rows),
            {
                "snapshot_count": 3,
                "first_snapshot_ts": "2026-05-20T12:00:00.000000Z",
                "last_snapshot_ts": "2026-05-20T12:00:20.000000Z",
                "median_gap_seconds": 10.0,
                "p95_gap_seconds": 15.0,
                "max_gap_seconds": 15.0,
                "valid_book_fraction": 1.0,
            },
        )


if __name__ == "__main__":
    unittest.main()
