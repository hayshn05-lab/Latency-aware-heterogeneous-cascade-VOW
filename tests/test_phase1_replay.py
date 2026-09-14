import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

class SnapshotReplayTests(unittest.TestCase):
    def test_next_snapshot_is_bounded_and_never_skips_invalid_first_book(self):
        from value_of_wait.phase1_replay import next_snapshot
        books = [{"ts": 100, "can_buy": False, "can_sell": False, "quality": "empty"}, {"ts": 200, "can_buy": True, "can_sell": True, "quality": "two_sided"}]
        self.assertEqual(next_snapshot(books, 90, 150)["ts"], 100)
        self.assertIsNone(next_snapshot(books, 101, 50))
        self.assertEqual(next_snapshot(books, 100, 0)["ts"], 100)

    def test_shared_engine_accounts_for_depth_fees_compute_and_actual_execution_times(self):
        from value_of_wait.phase1_replay import replay_actions
        books = {("rest", "yes"): [
            {"ts": 120, "quality": "two_sided", "can_buy": True, "can_sell": True, "asks": [[0.4, 20]], "bids": [[0.3, 20]], "min_order_size": 5},
            {"ts": 200, "quality": "two_sided", "can_buy": True, "can_sell": True, "asks": [[0.6, 20]], "bids": [[0.5, 20]], "min_order_size": 5}]}
        action = {"event_id": "e1", "condition_id": "c1", "asset_id": "yes", "source": "rest", "direction": "BUY_YES", "decision_ts": 90, "available_ts": 100, "exit_due_ts": 190, "quantity": 10, "limit_price": 1, "compute_cost": 0.1}
        result = replay_actions([action], books, {"initial_cash": 100, "fee_bps": 20, "max_wait_seconds": 100, "transport_seconds": 1})
        self.assertAlmostEqual(result["metrics"]["net_realized_pnl"], 0.882)
        self.assertAlmostEqual(result["metrics"]["cash"], 100.882)
        self.assertAlmostEqual(result["metrics"]["fees_paid"], 0.018)
        self.assertEqual(result["fills"][0]["ts"], 120)
        self.assertEqual(result["fills"][1]["ts"], 200)
        self.assertEqual(result["metrics"]["closed_positions"], 1)

    def test_action_expiry_prevents_filling_after_market_eligibility_ends(self):
        from value_of_wait.phase1_replay import replay_actions
        book = {"ts": 120, "quality": "ask_only", "can_buy": True, "can_sell": False, "asks": [[0.4, 20]], "bids": [], "min_order_size": 5}
        action = {"event_id": "e1", "condition_id": "c1", "asset_id": "yes", "source": "rest", "direction": "BUY_YES", "decision_ts": 90, "available_ts": 100, "expires_ts": 110, "exit_due_ts": 190, "quantity": 10, "limit_price": 1, "compute_cost": 0}
        result = replay_actions([action], {("rest", "yes"): [book]}, {"initial_cash": 100, "fee_bps": 0, "max_wait_seconds": 100, "transport_seconds": 1})
        self.assertEqual(result["metrics"]["entries"], 0)
        self.assertEqual(result["attempts"][0]["status"], "missing_entry")

if __name__ == "__main__":
    unittest.main()
