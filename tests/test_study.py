import tests
import unittest


class StudyTests(unittest.TestCase):
    def test_bundle_clean_flags_and_delay_metrics_obey_staleness(self):
        from value_of_wait.study import build_bundles, study_observations, summarize_delays

        tweets = [
            {"tweet_id": "a", "timestamp": "2026-05-20T10:00:00Z"},
            {"tweet_id": "b", "timestamp": "2026-05-20T10:00:30Z"},
            {"tweet_id": "c", "timestamp": "2026-05-20T10:02:00Z"},
        ]
        bundles = build_bundles(tweets, gap_seconds=60, horizons=[5, 120])
        trades = [{"timestamp": "2026-05-20T09:59:59Z", "yes_price": .40}, {"timestamp": "2026-05-20T10:00:31Z", "yes_price": .50}, {"timestamp": "2026-05-20T10:30:30Z", "yes_price": .60}]
        observations = study_observations(bundles[:1], {"m1": trades}, [5, 60, 1800], staleness_seconds=900, terminal_move_floor=.005)
        summary = summarize_delays(observations, [5, 60])

        self.assertTrue(bundles[0]["clean_5"])
        self.assertFalse(bundles[0]["clean_120"])
        self.assertEqual(observations[0]["updated"], True)
        self.assertEqual(observations[0]["absolute_repricing_points"], 10.0)
        self.assertEqual(summary[0]["clean_eligible_pairs"], 1)
        self.assertIsNone(summary[1]["median_repricing_points"])

    def test_first_print_is_strictly_after_decision_time(self):
        from value_of_wait.study import first_print_latencies

        bundles = [{"bundle_id": "b", "decision_time": "2026-05-20T10:00:00Z"}]
        trades = {"m": [{"timestamp": "2026-05-20T10:00:00Z", "yes_price": .4}, {"timestamp": "2026-05-20T10:00:07Z", "yes_price": .5}]}

        self.assertEqual(first_print_latencies(bundles, trades)[0]["latency_seconds"], 7.0)


if __name__ == "__main__":
    unittest.main()
