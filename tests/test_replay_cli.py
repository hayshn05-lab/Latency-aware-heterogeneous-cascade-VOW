from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from value_of_wait.replay_cli import main


class ReplayCliTests(unittest.TestCase):
    def test_build_routes_config_release_output_and_offline_flag(self):
        with tempfile.TemporaryDirectory() as temporary, patch("value_of_wait.replay_cli.build_starter_dataset", return_value={"evidence_tier": "H0"}) as build:
            root = Path(temporary)
            config = root / "config.json"
            config.write_text('{"dataset_version":"fixture"}', encoding="utf-8")
            release, output = root / "release", root / "output"
            exit_code = main(["build", "--config", str(config), "--release", str(release), "--output", str(output), "--offline"])
            self.assertEqual(exit_code, 0)
            build.assert_called_once_with({"dataset_version": "fixture"}, release, output, offline=True)


if __name__ == "__main__":
    unittest.main()
