from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from value_of_wait.reconciliation import capture_http


class ReconciliationErrorCaptureTests(unittest.TestCase):
    def test_http_error_is_captured_as_evidence_instead_of_raised(self) -> None:
        """Catches loss of a gated source's exact HTTP status and response body."""
        body = b'{"error":"terms must be accepted"}'
        url = "https://example.test/gated-dataset"

        def deny(_request: object, timeout: float) -> object:
            raise HTTPError(
                url,
                403,
                "Forbidden",
                {"Content-Type": "application/json"},
                BytesIO(body),
            )

        with tempfile.TemporaryDirectory() as temporary:
            try:
                record = capture_http(
                    url,
                    Path(temporary),
                    "gated",
                    opener=deny,
                    retrieved_at="2026-08-31T12:00:00Z",
                )
            except HTTPError:
                self.fail("HTTP errors must be captured as provenance, not raised")

            self.assertEqual(record["status"], 403)
            self.assertFalse(record["ok"])
            self.assertEqual(record["error_type"], "HTTPError")
            self.assertEqual(Path(temporary, record["body_file"]).read_bytes(), body)


if __name__ == "__main__":
    unittest.main()
