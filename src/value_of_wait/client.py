"""Small, standard-library Findata client with redacted provenance."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class MissingTokenError(RuntimeError):
    """Raised without echoing any credential value."""


def token_from_environment(environment: dict[str, str] | None = None) -> str:
    value = (environment if environment is not None else os.environ).get("LUMID_PAT", "")
    if not value:
        raise MissingTokenError("Findata authentication is not configured")
    return value


def _default_transport(url: str, headers: dict[str, str], timeout: float) -> Any:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:  # nosec B310: fixed caller-controlled base URL
        return json.loads(response.read().decode("utf-8"))


class FindataClient:
    def __init__(self, base_url: str, token: str, *, transport: Callable[[str, dict[str, str], float], Any] = _default_transport, retries: int = 3, sleeper: Callable[[float], None] = time.sleep) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._transport = transport
        self._retries = retries
        self._sleeper = sleeper
        self.request_records: list[dict[str, Any]] = []

    def get_json(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        clean_params = dict(sorted((params or {}).items()))
        query = urlencode(clean_params)
        url = f"{self.base_url}/{endpoint.lstrip('/')}" + (f"?{query}" if query else "")
        self.request_records.append({"endpoint": endpoint.lstrip("/"), "params": clean_params})
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json"}
        last_error: Exception | None = None
        for attempt in range(self._retries):
            try:
                return self._transport(url, headers, 30.0)
            except (OSError, ValueError) as error:
                last_error = error
                if attempt + 1 < self._retries:
                    self._sleeper(0.25 * (2 ** attempt))
        raise RuntimeError(self._error_summary(last_error)) from last_error

    def _error_summary(self, error: Exception | None) -> str:
        status = getattr(error, "code", None)
        reason = getattr(error, "reason", None)
        message = str(reason if reason is not None else error or "unknown service error")
        message = message.replace(self._token, "[REDACTED]")
        message = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)[^,;\s]+", r"\1[REDACTED]", message)
        message = re.sub(r"(?i)(token|api[_-]?key|password|secret)\s*([=:])\s*[^,;\s]+", r"\1\2[REDACTED]", message)
        message = " ".join(message.split())[:200]
        prefix = f"Findata request failed after retries (HTTP {status}" if status is not None else "Findata request failed after retries"
        return f"{prefix}: {message})" if status is not None else f"{prefix}: {message}"
