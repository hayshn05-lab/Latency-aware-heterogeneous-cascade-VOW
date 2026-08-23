import tests
import json
from pathlib import Path
import tempfile
import unittest


class PipelineTests(unittest.TestCase):
    def test_market_search_uses_live_parameter_names_and_stops_on_short_offset_page(self):
        from value_of_wait.pipeline import fetch_market_search

        class Client:
            def __init__(self):
                self.calls = []
            def get_json(self, endpoint, params):
                self.calls.append((endpoint, params))
                return {"data": {"items": [{"id": str(len(self.calls))}]}}

        client = Client()
        rows = fetch_market_search(client, "/prediction-markets/markets/search", {"q": "Elon Musk post", "venue": "polymarket", "status": "all", "limit": 2})

        self.assertEqual([row["id"] for row in rows], ["1"])
        self.assertEqual(client.calls, [("/prediction-markets/markets/search", {"q": "Elon Musk post", "venue": "polymarket", "status": "all", "limit": 2, "offset": 0})])

    def test_bounded_fetch_warns_when_service_total_exceeds_retrieved_rows(self):
        from value_of_wait.pipeline import fetch_bounded
        import warnings

        class Client:
            def get_json(self, endpoint, params):
                return {"data": {"items": [{"id": "one"}], "total": 2}}

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = fetch_bounded(Client(), "/tweets", {"since": "2026-05-19T16:00:00Z", "until": "2026-05-26T16:00:00Z", "limit": 1000})
        self.assertEqual(payload["data"]["items"], [{"id": "one"}])
        self.assertTrue(any("may be truncated" in str(item.message) for item in caught))

    def test_collection_uses_live_tweet_search_and_trade_parameters(self):
        from value_of_wait.pipeline import run_pilot

        class Client:
            def __init__(self):
                self.calls = []
            def get_json(self, endpoint, params):
                self.calls.append((endpoint, params))
                if endpoint == "/t/h": return {"data": [{"id": "t", "created_at": "2026-05-20T10:00:00Z"}]}
                if endpoint == "/s": return {"data": [{"id": "m"}]}
                if endpoint == "/d/m": return {"data": [{"condition_id": "0x08fe", "market_id": "2313560", "question": "Will Elon Musk post 10 times from May 19 to May 26, 2026?", "outcomes": ["Yes", "No"], "clob_token_ids": ["y", "n"], "outcome_prices": ["0.5", "0.5"]}]}
                return {"data": [{"token_id": "y", "price": .5, "timestamp": "2026-05-20T10:00:05Z"}]}

        with tempfile.TemporaryDirectory() as temporary:
            config = {"handle": "h", "window_start": "2026-05-19T16:00:00Z", "window_end": "2026-05-26T16:00:00Z", "search_query": "Elon Musk post", "title_prefix": "Will Elon Musk post", "title_window_label": "from May 19 to May 26, 2026", "bundle_gap_seconds": 60, "horizons_seconds": [5], "staleness_seconds": 900, "terminal_move_floor": .005, "cache_dir": str(Path(temporary) / "cache"), "endpoints": {"tweets": "/t/{handle}", "market_search": "/s", "market_detail": "/d/{condition_id}", "trades": "/r/{condition_id}", "orderbook": "/o/{asset_id}"}}
            client = Client()
            run_pilot(config, Path(temporary) / "output", offline=False, client=client)
        self.assertEqual(client.calls[0], ("/t/h", {"since": "2026-05-19T16:00:00Z", "until": "2026-05-26T16:00:00Z", "limit": 1000}))
        self.assertEqual(client.calls[1], ("/s", {"q": "Elon Musk post", "venue": "polymarket", "status": "all", "limit": 1000, "offset": 0}))
        self.assertEqual(client.calls[3], ("/r/0x08fe", {"from": "2026-05-19T16:00:00Z", "to": "2026-05-26T16:00:00Z", "limit": 1000}))

    def test_title_matching_accepts_exact_family_and_rejects_near_misses(self):
        from value_of_wait.pipeline import title_matches

        prefix = "Will Elon Musk post"
        window = "from May 19 to May 26, 2026"
        self.assertTrue(title_matches("Will Elon Musk post 100 or more times from May 19 to May 26, 2026?", prefix, window))
        self.assertFalse(title_matches("Will Elon Musk post 100 or more times from May 19 to May 27, 2026?", prefix, window))
        self.assertFalse(title_matches("Will Elon Musk post sometime from May 19 to May 26, 2026? extra", prefix, window))

    def test_configurable_endpoint_and_content_addressed_cache(self):
        from value_of_wait.pipeline import cache_request_key, load_cache_entry, save_cache_entry

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            endpoint = "/custom/tweets"
            first = {"handle": "one"}
            second = {"handle": "two"}
            save_cache_entry(cache, endpoint, first, {"data": [1]}, retrieved_at="2026-01-01T00:00:00Z")
            save_cache_entry(cache, endpoint, second, {"data": [2]}, retrieved_at="2026-01-01T00:00:00Z")
            self.assertNotEqual(cache_request_key(endpoint, first), cache_request_key(endpoint, second))
            self.assertEqual(load_cache_entry(cache, endpoint, second)[0], {"data": [2]})

    def test_precision_requires_three_nonzero_fractional_digits_in_both_streams(self):
        from value_of_wait.pipeline import timestamp_precision

        tweets = [{"timestamp": "2026-05-20T10:00:00.123Z"}]
        self.assertFalse(timestamp_precision(tweets, {"m": [{"timestamp": "2026-05-20T10:00:01.12Z"}]} )["milliseconds_identifiable"])
        self.assertFalse(timestamp_precision(tweets, {"m": [{"timestamp": "2026-05-20T10:00:01.000Z"}]} )["milliseconds_identifiable"])
        self.assertTrue(timestamp_precision(tweets, {"m": [{"timestamp": "2026-05-20T10:00:01.456Z"}]} )["milliseconds_identifiable"])

    def test_audit_writes_orderbook_coverage_without_execution_claim(self):
        from value_of_wait.pipeline import audit_pilot, save_cache_entry
        from value_of_wait.outputs import write_outputs

        with tempfile.TemporaryDirectory() as temporary:
            root, cache = Path(temporary), Path(temporary) / "cache"
            config = {"handle": "h", "window_start": "2026-05-19T16:00:00Z", "window_end": "2026-05-26T16:00:00Z", "search_query": "q", "title_prefix": "Will Elon Musk post", "title_window_label": "from May 19 to May 26, 2026", "cache_dir": str(cache), "endpoints": {"tweets": "/t/{handle}", "market_search": "/s", "market_detail": "/d/{condition_id}", "trades": "/r/{condition_id}", "orderbook": "/o/{asset_id}"}}
            tweet_period = {"since": config["window_start"], "until": config["window_end"], "limit": 1000}
            market_params = {"q": "q", "venue": "polymarket", "status": "all", "limit": 1000}
            period = {"from": config["window_start"], "to": config["window_end"], "limit": 1000}
            save_cache_entry(cache, "/t/h", tweet_period, {"data": []}); save_cache_entry(cache, "/s", market_params, {"data": [{"id": "m"}]})
            market = {"id": "m", "question": "Will Elon Musk post 10 times from May 19 to May 26, 2026?", "outcomes": [{"name": "YES", "token_id": "y"}, {"name": "NO", "token_id": "n"}]}
            save_cache_entry(cache, "/d/m", {}, {"data": [market]}); save_cache_entry(cache, "/r/m", period, {"data": []})
            save_cache_entry(cache, "/o/y", period, {"data": [{"timestamp": "2026-05-20T00:00:00Z"}]}); save_cache_entry(cache, "/o/n", period, {"data": []})
            audit_pilot(config, root / "audit", offline=True)
            self.assertIn("not execution-estimable", (root / "audit" / "audit_summary.json").read_text())
            self.assertTrue((root / "audit" / "orderbook_audit.csv").exists())
            self.assertTrue((root / "audit" / "audit_manifest.json").exists())
            self.assertFalse((root / "audit" / "data_manifest.json").exists())
            write_outputs(root / "audit", manifest=[], market_validation=[], bundles=[], observations=[], delay_profile=[], first_print=[])
            self.assertTrue((root / "audit" / "audit_manifest.json").exists())
            self.assertTrue((root / "audit" / "data_manifest.json").exists())

    def test_online_fixture_transport_uses_configured_endpoint_templates(self):
        from value_of_wait.client import FindataClient
        from value_of_wait.pipeline import run_pilot

        with tempfile.TemporaryDirectory() as temporary:
            calls = []
            def transport(url, headers, timeout):
                calls.append(url)
                if "/custom/tweets/h" in url: return {"data": [{"id": "t", "created_at": "2026-05-20T10:00:00Z"}]}
                if "/custom/search" in url: return {"data": [{"id": "m"}]}
                if "/custom/detail/m" in url: return {"data": [{"id": "m", "question": "Will Elon Musk post 10 times from May 19 to May 26, 2026?", "outcomes": [{"name": "YES", "token_id": "y"}, {"name": "NO", "token_id": "n"}]}]}
                return {"data": [{"token_id": "y", "price": .5, "timestamp": "2026-05-20T10:00:05Z"}]}
            config = {"handle": "h", "window_start": "2026-05-19T16:00:00Z", "window_end": "2026-05-26T16:00:00Z", "search_query": "q", "title_prefix": "Will Elon Musk post", "title_window_label": "from May 19 to May 26, 2026", "bundle_gap_seconds": 60, "horizons_seconds": [5], "staleness_seconds": 900, "terminal_move_floor": .005, "base_url": "https://fixture", "cache_dir": str(Path(temporary) / "cache"), "endpoints": {"tweets": "/custom/tweets/{handle}", "market_search": "/custom/search", "market_detail": "/custom/detail/{condition_id}", "trades": "/custom/trades/{condition_id}", "orderbook": "/custom/book/{asset_id}"}}
            run_pilot(config, Path(temporary) / "output", offline=False, client=FindataClient("https://fixture", "x", transport=transport))
            self.assertTrue(any("/custom/tweets/h" in url for url in calls))
            self.assertTrue(any("/custom/detail/m" in url for url in calls))
            self.assertTrue(any("/custom/trades/m" in url for url in calls))

    def test_offline_run_never_requires_token_and_writes_all_artifacts(self):
        from value_of_wait.pipeline import run_pilot, save_cache_entry

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            config = {"handle": "elonmusk", "window_start": "2026-05-19T16:00:00Z", "window_end": "2026-05-26T16:00:00Z", "search_query": "Elon Musk post", "title_prefix": "Will Elon Musk post", "title_window_label": "from May 19 to May 26, 2026", "bundle_gap_seconds": 60, "horizons_seconds": [5, 1800], "staleness_seconds": 900, "terminal_move_floor": .005, "base_url": "https://lum.id/findata", "cache_dir": str(cache), "endpoints": {"tweets": "/tweets/{handle}", "market_search": "/search", "market_detail": "/detail/{condition_id}", "trades": "/trades/{condition_id}", "orderbook": "/book/{asset_id}"}}
            tweet_period = {"since": config["window_start"], "until": config["window_end"], "limit": 1000}
            market_params = {"q": config["search_query"], "venue": "polymarket", "status": "all", "limit": 1000}
            trade_period = {"from": config["window_start"], "to": config["window_end"], "limit": 1000}
            save_cache_entry(cache, "/tweets/elonmusk", tweet_period, {"data": [{"id": "t", "created_at": "2026-05-20T10:00:00Z"}]})
            save_cache_entry(cache, "/search", market_params, {"data": [{"id": "m"}]})
            save_cache_entry(cache, "/detail/m", {}, {"data": [{"id": "m", "question": "Will Elon Musk post 100 or more times from May 19 to May 26, 2026?", "outcomes": [{"name": "YES", "token_id": "y"}, {"name": "NO", "token_id": "n"}]}]})
            save_cache_entry(cache, "/trades/m", trade_period, {"data": [{"token_id": "y", "price": .4, "timestamp": "2026-05-20T09:59:59Z"}, {"token_id": "y", "price": .5, "timestamp": "2026-05-20T10:00:05Z"}, {"token_id": "y", "price": .6, "timestamp": "2026-05-20T10:30:00Z"}]})
            output = root / "output"
            run_pilot(config, output, offline=True, environment={})

            self.assertTrue((output / "summary.json").exists())
            self.assertIn("included", (output / "market_validation.csv").read_text())


if __name__ == "__main__":
    unittest.main()
