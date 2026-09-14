from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.dataset_builder import event_author_allowed


class EventSourceFilterTests(unittest.TestCase):
    def test_market_venue_accounts_are_excluded_case_insensitively(self):
        excluded = ["Polymarket", "Kalshi"]
        self.assertFalse(event_author_allowed("polymarket", excluded))
        self.assertFalse(event_author_allowed("KALSHI", excluded))
        self.assertTrue(event_author_allowed("federalreserve", excluded))


if __name__ == "__main__":
    unittest.main()
