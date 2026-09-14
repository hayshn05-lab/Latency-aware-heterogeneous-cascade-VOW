from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self.status = 200
        self.headers = {
            "Content-Type": "application/json",
            "ETag": '"revision-1"',
            "Set-Cookie": "must-not-be-recorded",
        }

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class ReconciliationCaptureTests(unittest.TestCase):
    def test_capture_persists_exact_body_and_secret_free_provenance(self) -> None:
        """Catches lossy raw capture or persistence of an Authorization value."""
        try:
            from value_of_wait.reconciliation import capture_http
        except ModuleNotFoundError:
            self.fail("value_of_wait.reconciliation.capture_http is not implemented")

        body = b'{"rows":[{"condition_id":"0x01"}]}\n'
        secret = "pat-must-never-be-persisted"
        with tempfile.TemporaryDirectory() as temporary:
            record = capture_http(
                "https://example.test/table?limit=1",
                Path(temporary),
                "known-market",
                request_headers={"Authorization": f"Bearer {secret}"},
                opener=lambda _request, timeout: _Response(body),
                retrieved_at="2026-08-31T12:00:00Z",
            )
            body_path = Path(temporary, record["body_file"])
            provenance_path = Path(temporary, record["provenance_file"])
            provenance_bytes = provenance_path.read_bytes()

            self.assertEqual(body_path.read_bytes(), body)
            self.assertEqual(record["sha256"], hashlib.sha256(body).hexdigest())
            self.assertEqual(record["status"], 200)
            self.assertEqual(record["response_headers"], {
                "content-type": "application/json",
                "etag": '"revision-1"',
            })
            self.assertNotIn(secret.encode(), provenance_bytes)
            self.assertNotIn(b"authorization", provenance_bytes.lower())
            self.assertEqual(json.loads(provenance_bytes), record | {"provenance_file": record["provenance_file"]})


if __name__ == "__main__":
    unittest.main()
