from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest


class ReconciliationPlanTests(unittest.TestCase):
    def test_plan_captures_configured_source_and_writes_manifest(self) -> None:
        """Catches a capture plan that omits a configured source or its raw body."""
        try:
            from value_of_wait.reconciliation import run_capture_plan
        except ImportError:
            self.fail("value_of_wait.reconciliation.run_capture_plan is not implemented")

        config = {
            "targets": [{
                "auth": "none",
                "group": "docs",
                "name": "one",
                "url": "data:application/json,%7B%22ok%22%3Atrue%7D",
            }],
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            records = run_capture_plan(
                config,
                root,
                environment={},
                retrieved_at="2026-08-31T12:00:00Z",
            )

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["name"], "one")
            self.assertEqual(records[0]["status"], 200)
            self.assertEqual(
                Path(root, "docs", records[0]["body_file"]).read_bytes(),
                b'{"ok":true}',
            )
            manifest = json.loads(Path(root, "capture_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest, {"records": records})


if __name__ == "__main__":
    unittest.main()
