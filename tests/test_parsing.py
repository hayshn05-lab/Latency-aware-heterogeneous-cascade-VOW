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

    def test_market_accepts_live_parallel_outcomes_and_uses_condition_id(self):
        from value_of_wait.parsing import parse_markets

        markets = parse_markets({"data": [{"condition_id": "0x08fe", "market_id": "2313560", "question": "Will Elon Musk post 10 times from May 19 to May 26, 2026?", "outcomes": ["Yes", "No"], "clob_token_ids": ["yes-token", "no-token"], "outcome_prices": ["0.4", "0.6"]}]})

        self.assertEqual(markets[0]["market_id"], "0x08fe")
        self.assertEqual(markets[0]["source_market_id"], "2313560")
        self.assertEqual(markets[0]["outcome_tokens"], {"YES": "yes-token", "NO": "no-token"})

    def test_market_rejects_malformed_parallel_outcome_mappings(self):
        from value_of_wait.parsing import parse_markets

        base = {"condition_id": "0x08fe", "market_id": "2313560"}
        malformed = [
            {"outcomes": ["Yes", "No"], "clob_token_ids": ["yes-token"]},
            {"outcomes": ["Yes", "Yes"], "clob_token_ids": ["yes-token", "other-token"]},
            {"outcomes": ["Yes", "No", "Maybe"], "clob_token_ids": ["yes-token", "no-token", "maybe-token"]},
            {"outcomes": ["Yes", "No"], "clob_token_ids": ["yes-token", "yes-token"]},
            {"outcomes": ["Yes", "No"], "clob_token_ids": ["yes-token", ""]},
        ]

        for row in malformed:
            with self.subTest(row=row):
                self.assertEqual(parse_markets({"data": [base | row]}), [])

    def test_trade_parser_accepts_live_ts_and_canonicalizes_each_outcome(self):
        from value_of_wait.parsing import parse_trades

        trades = parse_trades({"data": [
            {"price": "0.60", "side": "BUY", "size": "5", "taker": "x", "token_id": "yes-token", "trade_id": "yes-trade", "ts": "2026-05-26T15:28:25Z"},
            {"price": "0.25", "side": "SELL", "size": "3", "taker": "y", "token_id": "no-token", "trade_id": "no-trade", "ts": "2026-05-26T15:28:26Z"},
        ]}, {"YES": "yes-token", "NO": "no-token"})

        self.assertEqual([(trade["timestamp"], trade["yes_price"]) for trade in trades], [("2026-05-26T15:28:25Z", 0.6), ("2026-05-26T15:28:26Z", 0.75)])

    def test_trade_parser_rejects_live_row_without_ts_or_other_timestamp(self):
        from value_of_wait.parsing import parse_trades

        trades = parse_trades({"data": [{"price": "0.60", "token_id": "yes-token", "trade_id": "yes-trade"}]}, {"YES": "yes-token", "NO": "no-token"})

        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
