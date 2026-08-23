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

    def test_paginated_search_reads_every_cursor_page(self):
        from value_of_wait.pipeline import fetch_paginated

        class Client:
            def __init__(self):
                self.calls = []
            def get_json(self, endpoint, params):
                self.calls.append((endpoint, params))
                return {"data": {"items": [{"id": str(len(self.calls))}], "next_cursor": "next" if len(self.calls) == 1 else None}}

        client = Client()
        rows = fetch_paginated(client, "markets", {"query": "Elon Musk post"})

        self.assertEqual([row["id"] for row in rows], ["1", "2"])
        self.assertEqual(client.calls[1][1]["cursor"], "next")


if __name__ == "__main__":
    unittest.main()
