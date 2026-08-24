import tests
import csv
import json
from pathlib import Path
import tempfile
import unittest


class OutputTests(unittest.TestCase):
    def test_chart_handles_missing_coverage_without_converting_it_to_zero(self):
        from value_of_wait.outputs import write_outputs

        with tempfile.TemporaryDirectory() as temporary:
            write_outputs(Path(temporary), manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=[{"horizon_seconds": 5, "updated_fraction": None, "clean_eligible_pairs": 0, "missing_pairs": 1}], first_print=[])
            svg = (Path(temporary) / "latency_profile.svg").read_text(encoding="utf-8")
            self.assertIn("updated=NA", svg)
            self.assertNotIn("stroke-dasharray", svg)

    def test_zero_profile_and_permuted_rows_produce_stable_chart_bytes(self):
        from value_of_wait.outputs import write_outputs

        profile = [{"horizon_seconds": 10, "clean_eligible_pairs": 2, "eligible_pairs": 2, "bundle_market_pairs": 2, "missing_pairs": 0, "updated_fraction": 0.0, "bundle_updated_n": 1, "median_bundle_updated_fraction": 0.0, "bundle_updated_iqr_low": 0.0, "bundle_updated_iqr_high": 0.0}]
        with tempfile.TemporaryDirectory() as temporary:
            left, right = Path(temporary) / "left", Path(temporary) / "right"
            kwargs = dict(manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=profile, first_print=[])
            write_outputs(left, **kwargs)
            write_outputs(right, **kwargs)
            svg = (left / "latency_profile.svg").read_bytes()
            self.assertEqual(svg, (right / "latency_profile.svg").read_bytes())
            self.assertIn(b"Updated fraction by delay", svg)
            self.assertIn(b"0%", svg)
            self.assertIn(b"updated=0.0%", svg)
            self.assertIn(b"stroke-dasharray", svg)

    def test_chart_renders_bundle_rate_iqr_as_descriptive_not_confidence_interval(self):
        from value_of_wait.outputs import write_outputs

        profile = [{"horizon_seconds": 5, "clean_eligible_pairs": 2, "updated_pairs": 1, "updated_fraction": .5, "bundle_updated_n": 2, "median_bundle_updated_fraction": .5, "bundle_updated_iqr_low": .25, "bundle_updated_iqr_high": .75, "missing_pairs": 0}]
        with tempfile.TemporaryDirectory() as temporary:
            write_outputs(Path(temporary), manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=profile, first_print=[])
            svg = (Path(temporary) / "latency_profile.svg").read_text(encoding="utf-8")
        self.assertIn("IQR across bundle-level update rates; descriptive heterogeneity, not a confidence interval", svg)
        self.assertIn("bundle n=2", svg)
        self.assertIn("stroke-dasharray", svg)

    def test_findings_call_out_absent_clean_support_and_split_sparse_high_age_evidence(self):
        from value_of_wait.outputs import write_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            absent = [{"horizon_seconds": 5, "clean_eligible_pairs": 0, "updated_fraction": None, "missing_pairs": 1}]
            split = [{"horizon_seconds": 5, "clean_eligible_pairs": 2, "updated_fraction": .1, "median_delayed_age_seconds": 1, "missing_pairs": 0}, {"horizon_seconds": 60, "clean_eligible_pairs": 2, "updated_fraction": 1.0, "median_delayed_age_seconds": 300, "missing_pairs": 0}]
            write_outputs(root / "absent", manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=absent, first_print=[])
            write_outputs(root / "split", manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=split, first_print=[])
            absent_text = (root / "absent" / "generated_findings.md").read_text(encoding="utf-8")
            split_text = (root / "split" / "generated_findings.md").read_text(encoding="utf-8")
        self.assertIn("No clean eligible support", absent_text)
        self.assertIn("weakly identified/under-resolved", split_text)

    def test_delay_csv_and_chart_follow_numeric_horizon_order(self):
        from value_of_wait.outputs import write_outputs

        profile = [{"horizon_seconds": horizon, "clean_eligible_pairs": 1, "missing_pairs": 0, "updated_fraction": 0.5} for horizon in [60, 5, 10]]
        with tempfile.TemporaryDirectory() as temporary:
            output, permuted = Path(temporary) / "ordered", Path(temporary) / "permuted"
            write_outputs(output, manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=profile, first_print=[])
            write_outputs(permuted, manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=list(reversed(profile)), first_print=[])
            with (output / "delay_profile.csv").open(newline="", encoding="utf-8") as handle:
                csv_rows = list(csv.DictReader(handle))
            svg = (output / "latency_profile.svg").read_text(encoding="utf-8")
            csv_bytes = (output / "delay_profile.csv").read_bytes()
            permuted_csv_bytes = (permuted / "delay_profile.csv").read_bytes()
        self.assertEqual([int(row["horizon_seconds"]) for row in csv_rows], [5, 10, 60])
        self.assertIn(">5s</text>", svg)
        self.assertLess(svg.index(">5s</text>"), svg.index(">10s</text>"))
        self.assertEqual(csv_bytes, permuted_csv_bytes)

    def test_findings_distinguish_sparse_under_resolved_and_dense_profiles(self):
        from value_of_wait.outputs import write_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sparse = [{"horizon_seconds": 5, "clean_eligible_pairs": 26, "updated_pairs": 1, "updated_fraction": 1 / 26, "median_delayed_age_seconds": 300, "missing_pairs": 0}]
            dense = [{"horizon_seconds": 5, "clean_eligible_pairs": 26, "updated_pairs": 26, "updated_fraction": 1.0, "median_delayed_age_seconds": 1, "missing_pairs": 0}]
            write_outputs(root / "sparse", manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=sparse, first_print=[], timestamp_precision={"classification": "seconds", "milliseconds_identifiable": False, "least_fractional_digits": 0})
            write_outputs(root / "dense", manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=dense, first_print=[], timestamp_precision={"classification": "seconds", "milliseconds_identifiable": False, "least_fractional_digits": 0})
            sparse_findings = (root / "sparse" / "generated_findings.md").read_text(encoding="utf-8")
            dense_findings = (root / "dense" / "generated_findings.md").read_text(encoding="utf-8")
        self.assertIn("timestamps are second-formatted", sparse_findings.lower())
        self.assertIn("milliseconds are not identifiable", sparse_findings)
        self.assertIn("weakly identified/under-resolved", sparse_findings)
        self.assertNotIn("weakly identified/under-resolved", dense_findings)
        self.assertIn("not profit", sparse_findings)

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
        self.assertEqual(summary["headline_support"], {"bundles": 1, "markets": 1, "observations": 1})
        self.assertIn("milliseconds are not identifiable", findings)


if __name__ == "__main__":
    unittest.main()
