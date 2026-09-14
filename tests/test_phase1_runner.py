import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

class RunnerTests(unittest.TestCase):
    def test_offline_cli_boundary_writes_complete_deterministic_artifacts(self):
        from value_of_wait.phase1_build import schema
        from value_of_wait.phase1_runner import run_experiment
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            c = sqlite3.connect(root / "db.sqlite")
            schema(c)
            c.execute("INSERT INTO p1_releases VALUES(?,?)", ("fixture", '{}'))
            post = {"event_id": "e", "source_ts": 90, "receipt_ts": 95, "text": "Election report", "author": "reporter"}
            c.execute("INSERT INTO p1_tweets VALUES(?,?,?,?,?,?)", ("fixture", "e", 90, 95, json.dumps(post), "hash"))
            c.commit()
            c.close()
            (root / "source.json").write_text(json.dumps({"release_id": "fixture"}), encoding="utf-8")
            config = {"database": str(root / "db.sqlite"), "data_manifest": str(root / "source.json"), "output": str(root / "out"), "mode": "conditional", "split": "development", "source": "rest", "cadence_seconds": 100, "feature_max_age_seconds": 300, "lookback_seconds": 900, "top_k": 10, "retrieval_seconds": 1, "exit_horizon_seconds": 1800, "initial_cash": 1000, "fee_bps": 20, "quantity": 10, "max_wait_seconds": 900, "transport_seconds": 1, "min_edge": 0.02, "momentum_threshold": 0.02}
            result = run_experiment(config, "no_trade")
            self.assertEqual(result["metrics"]["events"], 1)
            self.assertEqual(result["metrics"]["cash"], 1000)
            files = {p.name: p.read_bytes() for p in Path(result["output"]).iterdir() if p.is_file()}
            again = run_experiment(config, "no_trade")
            self.assertEqual(files, {p.name: p.read_bytes() for p in Path(again["output"]).iterdir() if p.is_file()})
            self.assertIn("data_manifest.json", files)
            self.assertIn("actions.jsonl", files)
            self.assertIn("observations.jsonl", files)

if __name__ == "__main__":
    unittest.main()
