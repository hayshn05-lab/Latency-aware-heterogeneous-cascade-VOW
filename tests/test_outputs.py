import tests
import json
from pathlib import Path
import tempfile
import unittest


class OutputTests(unittest.TestCase):
    def test_writers_produce_deterministic_redacted_artifacts(self):
        from value_of_wait.outputs import write_outputs

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            write_outputs(output, manifest=[{"endpoint": "tweets", "params": {"limit": 1}, "retrieved_at": "2026-01-01T00:00:00Z", "row_count": 2, "sha256": "abc"}], market_validation=[{"market_id": "m", "decision": "included", "reason": "unambiguous YES/NO mapping"}], bundles=[{"bundle_id": "b", "decision_time": "2026-01-01T00:00:00Z"}], observations=[{"bundle_id": "b", "market_id": "m", "horizon_seconds": 5, "eligible": True}], delay_profile=[{"horizon_seconds": 5, "clean_eligible_pairs": 1, "median_repricing_points": 2.0, "missing_pairs": 0}], first_print=[{"bundle_id": "b", "latency_seconds": 5.0}])
            files = {path.name for path in output.iterdir()}
            summary = json.loads((output / "summary.json").read_text())
            findings = (output / "generated_findings.md").read_text()

        self.assertTrue({"data_manifest.json", "market_validation.csv", "event_bundles.csv", "delay_profile.csv", "first_print_latency.csv", "observations.csv", "summary.json", "latency_profile.svg", "generated_findings.md"} <= files)
        self.assertEqual(summary["economic_label"], "non-executable price-move proxy")
        self.assertIn("milliseconds are not identifiable", findings)


if __name__ == "__main__":
    unittest.main()
