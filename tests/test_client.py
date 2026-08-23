import tests
import unittest


class ClientTests(unittest.TestCase):
    def test_client_retries_and_redacts_authorization(self):
        from value_of_wait.client import FindataClient

        calls = []
        def transport(url, headers, timeout):
            calls.append(headers)
            if len(calls) == 1:
                raise OSError("temporary")
            return {"data": []}

        client = FindataClient("https://example.test", "secret-value", transport=transport, retries=2, sleeper=lambda _: None)
        payload = client.get_json("tweets", {"cursor": "abc"})

        self.assertEqual(payload, {"data": []})
        self.assertEqual(len(calls), 2)
        self.assertNotIn("secret-value", str(client.request_records))
        self.assertEqual(client.request_records[0]["params"], {"cursor": "abc"})

    def test_missing_token_does_not_echo_environment_value(self):
        from value_of_wait.client import MissingTokenError, token_from_environment

        with self.assertRaises(MissingTokenError) as error:
            token_from_environment({})
        self.assertNotIn("LUMID_PAT=", str(error.exception))

    def test_market_search_reads_every_offset_page_until_total(self):
        from value_of_wait.pipeline import fetch_market_search

        class Client:
            def __init__(self):
                self.calls = []
            def get_json(self, endpoint, params):
                self.calls.append((endpoint, params))
                return {"data": {"items": [{"id": str(len(self.calls))}], "total": 2}}

        client = Client()
        rows = fetch_market_search(client, "markets", {"q": "Elon Musk post", "venue": "polymarket", "status": "all", "limit": 1})

        self.assertEqual([row["id"] for row in rows], ["1", "2"])
        self.assertEqual(client.calls[0][1]["offset"], 0)
        self.assertEqual(client.calls[1][1]["offset"], 1)

    def test_client_error_includes_status_and_redacts_credential(self):
        from value_of_wait.client import FindataClient

        class ServiceError(OSError):
            code = 400
            reason = "unsupported parameter query; Authorization: Bearer service-secret; https://service.test?access_token=url-secret"

        client = FindataClient("https://example.test", "secret-value", transport=lambda *_: (_ for _ in ()).throw(ServiceError()), retries=1)
        with self.assertRaisesRegex(RuntimeError, r"HTTP 400.*unsupported parameter") as error:
            client.get_json("markets", {"q": "Elon Musk"})
        self.assertNotIn("secret-value", str(error.exception))
        self.assertNotIn("service-secret", str(error.exception))
        self.assertNotIn("url-secret", str(error.exception))

    def test_cache_rejects_multiple_content_versions_for_one_request(self):
        from pathlib import Path
        import tempfile
        from value_of_wait.pipeline import load_cache_entry, save_cache_entry

        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary)
            save_cache_entry(cache, "/endpoint", {"a": 1}, {"data": [1]})
            save_cache_entry(cache, "/endpoint", {"a": 1}, {"data": [2]})
            with self.assertRaisesRegex(RuntimeError, "multiple content versions"):
                load_cache_entry(cache, "/endpoint", {"a": 1})


if __name__ == "__main__":
    unittest.main()
