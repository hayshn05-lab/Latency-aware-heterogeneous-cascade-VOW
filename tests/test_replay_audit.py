import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.replay_audit import (
    ReplayValidationError,
    build_overlap_funnel,
    normalize_market_tokens,
    parse_l2_snapshot,
    select_asof_snapshot,
    validate_book,
    validate_split_integrity,
    walk_market_order,
    write_audit_release,
)


CONDITION_A = "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
CONDITION_B = "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"


class MarketTokenContractTests(unittest.TestCase):
    def test_parallel_outcomes_preserve_numeric_market_alias(self):
        row = {
            "condition_id": CONDITION_A.upper().replace("0X", "0x"),
            "market_id": "2169995",
            "outcomes": ["Yes", "No"],
            "clob_token_ids": ["111", "222"],
        }
        self.assertEqual(
            normalize_market_tokens(row),
            {
                "condition_id": CONDITION_A,
                "source_market_id": "2169995",
                "yes_asset_id": "111",
                "no_asset_id": "222",
            },
        )

    def test_object_outcomes_are_mapped_by_label_not_position(self):
        row = {
            "condition_id": CONDITION_A,
            "outcomes": [
                {"name": "NO", "token_id": "222"},
                {"name": "YES", "token_id": "111"},
            ],
        }
        actual = normalize_market_tokens(row)
        self.assertEqual(actual["yes_asset_id"], "111")
        self.assertEqual(actual["no_asset_id"], "222")

    def test_invalid_condition_or_ambiguous_assets_fail_closed(self):
        bad_condition = {
            "condition_id": "2169995",
            "outcomes": ["Yes", "No"],
            "clob_token_ids": ["111", "222"],
        }
        duplicate_assets = {
            "condition_id": CONDITION_A,
            "outcomes": ["Yes", "No"],
            "clob_token_ids": ["111", "111"],
        }
        with self.assertRaisesRegex(ReplayValidationError, "condition_id"):
            normalize_market_tokens(bad_condition)
        with self.assertRaisesRegex(ReplayValidationError, "distinct"):
            normalize_market_tokens(duplicate_assets)


class L2ContractTests(unittest.TestCase):
    def test_l2_object_and_pair_levels_are_normalized_and_sorted(self):
        row = {
            "asset_id": "111",
            "condition_id": CONDITION_A,
            "snapshot_ts": "2026-05-20T12:00:04.500Z",
            "bids": [{"price": "0.48", "size": "5"}, {"price": "0.49", "size": "2"}],
            "asks": [["0.52", "3"], ["0.51", "2"]],
            "hash": "book-a",
        }
        actual = parse_l2_snapshot(row)
        self.assertEqual(actual["snapshot_ts"], "2026-05-20T12:00:04.500000Z")
        self.assertEqual(actual["bids"], [{"price": "0.49", "size": "2"}, {"price": "0.48", "size": "5"}])
        self.assertEqual(actual["asks"], [{"price": "0.51", "size": "2"}, {"price": "0.52", "size": "3"}])
        self.assertEqual(validate_book(actual), "valid")

    def test_malformed_crossed_and_one_sided_books_fail_quality_gate(self):
        with self.assertRaisesRegex(ReplayValidationError, "level"):
            parse_l2_snapshot(
                {
                    "asset_id": "111",
                    "snapshot_ts": "2026-05-20T12:00:00Z",
                    "bids": [{"price": "bad", "size": "1"}],
                    "asks": [],
                }
            )
        crossed = parse_l2_snapshot(
            {
                "asset_id": "111",
                "snapshot_ts": "2026-05-20T12:00:00Z",
                "bids": [["0.52", "1"]],
                "asks": [["0.51", "1"]],
            }
        )
        one_sided = parse_l2_snapshot(
            {
                "asset_id": "111",
                "snapshot_ts": "2026-05-20T12:00:00Z",
                "bids": [["0.49", "1"]],
                "asks": [],
            }
        )
        self.assertEqual(validate_book(crossed), "crossed_book")
        self.assertEqual(validate_book(one_sided), "missing_side")

    def test_asof_uses_latest_nonfuture_snapshot_and_rejects_stale_state(self):
        rows = [
            parse_l2_snapshot(
                {
                    "asset_id": "111",
                    "snapshot_ts": "2026-05-20T12:00:00Z",
                    "bids": [["0.48", "1"]],
                    "asks": [["0.52", "1"]],
                }
            ),
            parse_l2_snapshot(
                {
                    "asset_id": "111",
                    "snapshot_ts": "2026-05-20T12:00:04Z",
                    "bids": [["0.49", "1"]],
                    "asks": [["0.51", "1"]],
                }
            ),
            parse_l2_snapshot(
                {
                    "asset_id": "111",
                    "snapshot_ts": "2026-05-20T12:00:06Z",
                    "bids": [["0.50", "1"]],
                    "asks": [["0.51", "1"]],
                }
            ),
        ]
        selected = select_asof_snapshot(rows, "2026-05-20T12:00:05Z", max_age_seconds=1)
        self.assertEqual(selected["snapshot"]["snapshot_ts"], "2026-05-20T12:00:04.000000Z")
        self.assertEqual(selected["age_seconds"], 1.0)
        with self.assertRaisesRegex(ReplayValidationError, "stale"):
            select_asof_snapshot(rows, "2026-05-20T12:00:12Z", max_age_seconds=5)
        with self.assertRaisesRegex(ReplayValidationError, "at or before"):
            select_asof_snapshot(rows[2:], "2026-05-20T12:00:05Z", max_age_seconds=5)

    def test_depth_walk_is_deterministic_and_reports_partial_fill(self):
        book = parse_l2_snapshot(
            {
                "asset_id": "111",
                "snapshot_ts": "2026-05-20T12:00:00Z",
                "bids": [["0.49", "2"], ["0.48", "5"]],
                "asks": [["0.51", "2"], ["0.52", "3"]],
            }
        )
        fill = walk_market_order(book, side="buy", quantity="4", fee_bps="10")
        self.assertEqual(
            fill,
            {
                "side": "buy",
                "requested_quantity": "4",
                "filled_quantity": "4",
                "full_fill": True,
                "gross_notional": "2.06",
                "average_price": "0.515",
                "fee": "0.00206",
                "net_cash_flow": "-2.06206",
                "levels_consumed": 2,
            },
        )
        partial = walk_market_order(book, side="buy", quantity="6", fee_bps="0")
        self.assertFalse(partial["full_fill"])
        self.assertEqual(partial["filled_quantity"], "5")


class PointInTimeAndReleaseTests(unittest.TestCase):
    def test_family_split_leakage_and_embargo_are_rejected(self):
        with self.assertRaisesRegex(ReplayValidationError, "family"):
            validate_split_integrity(
                [
                    {"family_id": "f1", "split": "train", "event_ts": "2026-01-01T00:00:00Z"},
                    {"family_id": "f1", "split": "test", "event_ts": "2026-03-01T00:00:00Z"},
                ],
                embargo_seconds=60,
            )
        with self.assertRaisesRegex(ReplayValidationError, "embargo"):
            validate_split_integrity(
                [
                    {"family_id": "f1", "split": "train", "event_ts": "2026-01-01T00:00:00Z"},
                    {"family_id": "f2", "split": "validation", "event_ts": "2026-01-01T00:00:59Z"},
                ],
                embargo_seconds=60,
            )
        actual = validate_split_integrity(
            [
                {"family_id": "f1", "split": "train", "event_ts": "2026-01-01T00:00:00Z"},
                {"family_id": "f2", "split": "validation", "event_ts": "2026-01-01T00:01:00Z"},
            ],
            embargo_seconds=60,
        )
        self.assertEqual(actual, {"families": 2, "rows": 2, "splits": ["train", "validation"]})

    def test_overlap_funnel_is_nested_and_reports_independent_families(self):
        records = [
            {"event_id": "e1", "family_id": "f1", "pit_active_verified": True, "historical_l2_window": True, "valid_books": True, "verified_outcome": True},
            {"event_id": "e2", "family_id": "f1", "pit_active_verified": True, "historical_l2_window": True, "valid_books": False, "verified_outcome": True},
            {"event_id": "e3", "family_id": "f2", "pit_active_verified": False, "historical_l2_window": False, "valid_books": False, "verified_outcome": False},
        ]
        self.assertEqual(
            build_overlap_funnel(records),
            [
                {"stage": 1, "name": "candidate_external_events", "rows": 3, "independent_families": 2},
                {"stage": 2, "name": "point_in_time_active_markets", "rows": 2, "independent_families": 1},
                {"stage": 3, "name": "historical_l2_window", "rows": 2, "independent_families": 1},
                {"stage": 4, "name": "valid_entry_deep_exit_books", "rows": 1, "independent_families": 1},
                {"stage": 5, "name": "verified_outcomes", "rows": 1, "independent_families": 1},
                {"stage": 6, "name": "independent_event_families", "rows": 1, "independent_families": 1},
            ],
        )

    def test_release_reconstruction_is_byte_deterministic(self):
        summary = {"verdict": "H0", "strict_effective_n": 0}
        funnel = [
            {"stage": 2, "name": "point_in_time_active_markets", "rows": 0, "independent_families": 0},
            {"stage": 1, "name": "candidate_external_events", "rows": 2, "independent_families": 2},
        ]
        coverage = [
            {"asset_id": "222", "snapshot_count": 0},
            {"asset_id": "111", "snapshot_count": 3},
        ]
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            write_audit_release(Path(first), summary=summary, funnel=funnel, l2_coverage=coverage)
            write_audit_release(Path(second), summary=dict(reversed(list(summary.items()))), funnel=list(reversed(funnel)), l2_coverage=list(reversed(coverage)))
            names = ["audit_summary.json", "funnel.csv", "l2_coverage.csv", "reconstruction_manifest.json"]
            for name in names:
                self.assertEqual((Path(first) / name).read_bytes(), (Path(second) / name).read_bytes(), name)
            manifest = json.loads((Path(first) / "reconstruction_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual([row["path"] for row in manifest["artifacts"]], ["audit_summary.json", "funnel.csv", "l2_coverage.csv"])


if __name__ == "__main__":
    unittest.main()
