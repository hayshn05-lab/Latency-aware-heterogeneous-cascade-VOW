import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

class InterfaceTests(unittest.TestCase):
    def test_observation_retrieves_only_available_markets_and_past_features(self):
        from value_of_wait.phase1_interface import make_observation
        post = {"event_id": "e", "source_ts": 90, "receipt_ts": 95, "text": "Election news", "author": "reporter"}
        markets = [{"condition_id": "a", "question": "Election result?", "yes_asset_id": "yes", "no_asset_id": "no", "available_from": 0, "available_until": 1000, "family_id": "f", "metadata_basis": "conditional"}, {"condition_id": "b", "question": "Election news?", "yes_asset_id": "y2", "no_asset_id": "n2", "available_from": 200, "available_until": 1000, "family_id": "g", "metadata_basis": "conditional"}]
        books = {("rest", "yes"): [{"ts": 50, "can_buy": True, "can_sell": True, "asks": [[0.5, 10]], "bids": [[0.3, 10]]}, {"ts": 150, "can_buy": True, "can_sell": True, "asks": [[0.95, 10]], "bids": [[0.85, 10]]}]}
        settings = {"cadence_seconds": 100, "source": "rest", "feature_max_age_seconds": 100, "lookback_seconds": 30, "top_k": 10, "retrieval_seconds": 1, "exit_horizon_seconds": 1800}
        obs = make_observation(post, markets, books, settings)
        self.assertEqual(obs["decision_ts"], 100)
        self.assertEqual([x["condition_id"] for x in obs["candidates"]], ["a"])
        self.assertEqual(obs["candidates"][0]["features"]["yes_mid"], 0.4)
        self.assertNotIn("books", obs)
        self.assertNotIn("labels", obs)

    def test_confidence_cascade_only_calls_deep_after_gate_and_charges_both_paths(self):
        from value_of_wait.phase1_interface import decide
        obs = {"event_id": "e", "decision_ts": 100, "input_cutoff_ts": 100, "retrieval_complete_ts": 101, "exit_due_ts": 1900, "source": "rest", "context_sha256": "context", "candidates": [{"condition_id": "c", "yes_asset_id": "y", "no_asset_id": "n", "family_id": "f", "available_until": 5000, "retrieval_score": 1, "features": {"yes_ask": 0.4, "no_ask": 0.7, "yes_mid": 0.35, "momentum": 0.03}}]}
        calls = []
        def predictor(path, observation):
            calls.append(path)
            return {"event_id": "e", "context_sha256": "context", "input_cutoff_ts": 100, "condition_id": "c", "expected_yes_price": 0.8, "confidence": 0.5 if path == "fast" else 0.9, "latency_seconds": 2 if path == "fast" else 60, "compute_cost": 0.01 if path == "fast" else 0.1}
        settings = {"confidence_threshold": 0.7, "min_edge": 0.02, "quantity": 10, "fee_bps": 20, "inference_seconds": 0, "momentum_threshold": 0.02}
        action = decide("confidence_cascade", obs, settings, predictor)
        self.assertEqual(calls, ["fast", "deep"])
        self.assertEqual(action["available_ts"], 163)
        self.assertAlmostEqual(action["compute_cost"], 0.11)
        self.assertEqual(action["asset_id"], "y")
        calls.clear()
        settings["confidence_threshold"] = 0.4
        action = decide("confidence_cascade", obs, settings, predictor)
        self.assertEqual(calls, ["fast"])
        self.assertEqual(action["available_ts"], 103)

    def test_deep_evidence_excludes_future_receipts_and_preserves_fast_context(self):
        from value_of_wait.phase1_interface import deep_context
        obs = {"event_id": "e", "input_cutoff_ts": 100, "text": "Election result", "context_sha256": "fast", "candidates": []}
        corpus = [{"event_id": "old", "receipt_ts": 90, "source_ts": 80, "text": "Election report", "author": "r"}, {"event_id": "future", "receipt_ts": 110, "source_ts": 80, "text": "Election result", "author": "r"}]
        result = deep_context(obs, corpus, lookback_seconds=100, top_k=5)
        self.assertEqual([x["event_id"] for x in result["historical_evidence"]], ["old"])
        self.assertNotIn("historical_evidence", obs)
        self.assertNotEqual(result["context_sha256"], "fast")

if __name__ == "__main__":
    unittest.main()
