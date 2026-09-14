import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

class MetricTests(unittest.TestCase):
    def test_vow_uses_same_deep_action_and_keeps_compute_separate(self):
        from value_of_wait.phase1_metrics import counterfactual_pair
        def book(ts, ask, bid):
            return {"ts": ts, "can_buy": True, "can_sell": True, "asks": [[ask, 100]], "bids": [[bid, 100]], "min_order_size": 1}
        tape = {("rest", "yes"): [book(120, 0.4, 0.3), book(180, 0.5, 0.4), book(200, 0.7, 0.6)]}
        fast = {"event_id": "e", "direction": "NONE", "decision_ts": 90, "available_ts": 100, "exit_due_ts": 190, "compute_cost": 0}
        deep = dict(fast, direction="BUY_YES", condition_id="c", asset_id="yes", source="rest", quantity=10, limit_price=1, available_ts=160, compute_cost=0.2)
        result = counterfactual_pair(fast, deep, tape, {"initial_cash": 100, "fee_bps": 0, "max_wait_seconds": 100, "transport_seconds": 1})
        self.assertEqual(result["G"], 2)
        self.assertEqual(result["W"], -1)
        self.assertEqual(result["VOW"], 1)
        self.assertAlmostEqual(result["VOW_after_incremental_compute"], 0.8)
        self.assertFalse(result["same_deep_entry_snapshot"])

if __name__ == "__main__":
    unittest.main()
