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
        self.assertIsNotNone(summary[0]["median_delayed_age_seconds"])
        self.assertIsNone(summary[1]["median_repricing_points"])

    def test_first_print_is_strictly_after_decision_time(self):
        from value_of_wait.study import first_print_latencies

        bundles = [{"bundle_id": "b", "decision_time": "2026-05-20T10:00:00Z", "clean_1800": True}]
        trades = {"m": [{"timestamp": "2026-05-20T10:00:00Z", "yes_price": .4}, {"timestamp": "2026-05-20T10:00:07Z", "yes_price": .5}]}

        latency = first_print_latencies(bundles, trades, terminal_horizon_seconds=1800)[0]
        self.assertEqual(latency["latency_seconds"], 7.0)
        self.assertTrue(latency["within_terminal_horizon"])
        self.assertTrue(latency["terminal_clean"])
        late = first_print_latencies(bundles, trades, terminal_horizon_seconds=5)[0]
        self.assertFalse(late["within_terminal_horizon"])

    def test_remaining_move_requires_terminal_cleanliness_and_summary_uses_actual_sample_counts(self):
        from value_of_wait.study import build_bundles, study_observations, summarize_delays

        tweets = [{"tweet_id": "a", "timestamp": "2026-05-20T10:00:00Z"}, {"tweet_id": "later", "timestamp": "2026-05-20T10:01:00Z"}]
        bundles = build_bundles(tweets, gap_seconds=0, horizons=[5, 1800])
        trades = {"m": [{"timestamp": "2026-05-20T09:59:59Z", "yes_price": .4}, {"timestamp": "2026-05-20T10:00:03Z", "yes_price": .5}, {"timestamp": "2026-05-20T10:30:00Z", "yes_price": .6}]}

        observations = study_observations(bundles[:1], trades, [5, 1800], staleness_seconds=900, terminal_move_floor=.005)
        short = observations[0]
        summary = summarize_delays(observations, [5])[0]

        self.assertTrue(short["clean"])
        self.assertTrue(short["eligible"])
        self.assertTrue(short["updated"])
        self.assertIsNone(short["remaining_move_proxy"])
        self.assertEqual(summary["updated_pairs"], 1)
        self.assertEqual(summary["repricing_n"], 1)
        self.assertEqual(summary["remaining_n"], 0)
        self.assertEqual(summary["terminal_clean_eligible_pairs"], 0)

    def test_summary_reports_bundle_level_update_rate_distribution(self):
        from value_of_wait.study import summarize_delays

        observations = [
            {"bundle_id": "b1", "horizon_seconds": 5, "eligible": True, "clean": True, "terminal_clean": True, "updated": True, "absolute_repricing_points": 1, "remaining_move_proxy": None, "delayed_age_seconds": 1},
            {"bundle_id": "b1", "horizon_seconds": 5, "eligible": True, "clean": True, "terminal_clean": True, "updated": False, "absolute_repricing_points": 0, "remaining_move_proxy": None, "delayed_age_seconds": 1},
            {"bundle_id": "b2", "horizon_seconds": 5, "eligible": True, "clean": True, "terminal_clean": True, "updated": True, "absolute_repricing_points": 1, "remaining_move_proxy": None, "delayed_age_seconds": 1},
        ]

        summary = summarize_delays(observations, [5])[0]

        self.assertEqual(summary["updated_fraction"], 2 / 3)
        self.assertEqual(summary["bundle_updated_n"], 2)
        self.assertEqual(summary["median_bundle_updated_fraction"], 0.75)
        self.assertEqual((summary["bundle_updated_iqr_low"], summary["bundle_updated_iqr_high"]), (0.5, 0.5))


if __name__ == "__main__":
    unittest.main()
