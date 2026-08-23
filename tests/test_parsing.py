import tests
import unittest


class ParsingTests(unittest.TestCase):
    def test_parsers_accept_common_envelopes_and_canonicalize_no_trades(self):
        from value_of_wait.parsing import parse_markets, parse_trades, parse_tweets

        markets = parse_markets({"data": {"items": [{"id": "m1", "question": "How many Elon Musk posts?", "outcomes": [{"name": "YES", "token_id": "yes"}, {"name": "NO", "token_id": "no"}]}]}})
        tweets = parse_tweets({"results": [{"id": "t1", "created_at": "2026-05-20T10:00:00Z"}]})
        trades = parse_trades({"data": [{"token_id": "no", "price": "0.25", "timestamp": "2026-05-20T10:00:01Z"}]}, {"yes": "yes", "no": "no"})

        self.assertEqual(markets[0]["outcome_tokens"], {"YES": "yes", "NO": "no"})
        self.assertEqual(tweets[0]["timestamp"], "2026-05-20T10:00:00Z")
        self.assertEqual(trades[0]["yes_price"], 0.75)

    def test_market_with_ambiguous_outcomes_is_rejected(self):
        from value_of_wait.parsing import parse_markets

        markets = parse_markets({"markets": [{"id": "m1", "outcomes": [{"name": "YES", "token_id": "a"}, {"name": "YES", "token_id": "b"}]}]})

        self.assertEqual(markets, [])


if __name__ == "__main__":
    unittest.main()
