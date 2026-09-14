import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "week6 report"
sys.path.insert(0, str(ROOT))

class TrialTests(unittest.TestCase):
    def test_cascade_routes_only_uncertain_cases_and_counts_shared_stage_once(self):
        from trial_frugalgpt import run
        calls = []
        def fake(model, prompt, **kwargs):
            calls.append((model, prompt))
            ids = ["D"] if len(calls) == 3 else list("ABCD")
            labels = ["SUPPORTS_YES", "CONTRADICTS_YES", "IRRELEVANT", "INSUFFICIENT"]
            return {"answer": {"items": [{"id": i, "label": labels[ord(i)-65], "confidence": .95 if i == "D" else .99} for i in ids]}, "seconds": 1, "total_tokens": 10}
        result = run(fake)
        self.assertEqual(result["escalated_ids"], ["D"])
        self.assertEqual(result["cascade"]["total_tokens"], 20)
        self.assertEqual(result["cascade"]["correct"], 4)
        self.assertNotIn('"id": "A"', calls[2][1])

    def test_forecasts_preserve_failed_attempt(self):
        from trial_timeseek import run
        def fake(model, prompt, **kwargs):
            return {"answer": None, "error": "No JSON answer", "seconds": 1, "total_tokens": 400}
        result = run(fake)
        self.assertEqual(len(result["attempts"]), 2)
        self.assertEqual(result["valid_calls"], 0)

    def test_remote_url_rejected_before_transport(self):
        from trial_common import request
        with self.assertRaises(ValueError):
            request("https://example.com/steal", token="never-send")
