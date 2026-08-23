import tests
import os
from pathlib import Path
import tempfile
import unittest


class CliTests(unittest.TestCase):
    def test_audit_command_is_routed_to_audit_mode(self):
        from unittest.mock import patch
        from value_of_wait.cli import main

        with tempfile.TemporaryDirectory() as temporary, patch("value_of_wait.cli.audit_pilot") as audit:
            config = Path(temporary) / "config.json"
            config.write_text("{}")
            self.assertEqual(main(["audit", "--offline", "--config", str(config), "--output", temporary]), 0)
            audit.assert_called_once()
    def test_online_mode_without_token_returns_exit_two(self):
        from value_of_wait.cli import main

        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "config.json"
            config.write_text('{"base_url":"https://lum.id/findata"}')
            previous = os.environ.pop("LUMID_PAT", None)
            try:
                exit_code = main(["audit", "--config", str(config), "--output", str(Path(temporary) / "output")])
            finally:
                if previous is not None:
                    os.environ["LUMID_PAT"] = previous

        self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
