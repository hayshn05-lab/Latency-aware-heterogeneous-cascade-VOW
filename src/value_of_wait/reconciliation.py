"""Secret-safe, content-addressed captures for source reconciliation."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.request import Request, urlopen


_SAFE_RESPONSE_HEADERS = ("content-type", "etag", "last-modified", "x-repo-commit")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._") or "response"


def capture_http(
    url: str,
    output: Path,
    name: str,
    *,
    request_headers: Mapping[str, str] | None = None,
    opener: Callable[..., Any] = urlopen,
    timeout: float = 30.0,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    """Persist exact response bytes and a credential-free provenance record."""
    request = Request(url, headers=dict(request_headers or {}))
    error_type: str | None = None
    try:
        with opener(request, timeout=timeout) as response:
            body = response.read()
            status = int(getattr(response, "status", None) or 200)
            headers = response.headers
    except HTTPError as error:
        body = error.read()
        status = int(error.code)
        headers = error.headers
        error_type = "HTTPError"
    observed_headers = {
        str(key).lower(): str(value)
        for key, value in headers.items()
    }
    response_headers = {
        key: observed_headers[key]
        for key in _SAFE_RESPONSE_HEADERS
        if key in observed_headers
    }

    output.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(body).hexdigest()
    stem = f"{_safe_name(name)}-{digest}"
    body_path = output / f"{stem}.body"
    provenance_path = output / f"{stem}.provenance.json"
    if body_path.exists() and body_path.read_bytes() != body:
        raise RuntimeError(f"content-address collision for {body_path.name}")
    body_path.write_bytes(body)
    record: dict[str, Any] = {
        "body_file": body_path.name,
        "byte_count": len(body),
        "provenance_file": provenance_path.name,
        "retrieved_at": retrieved_at or _utc_now(),
        "response_headers": response_headers,
        "ok": error_type is None,
        "sha256": digest,
        "status": status,
        "url": url,
    }
    if error_type is not None:
        record["error_type"] = error_type
    provenance_path.write_text(
        json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    return record


def run_capture_plan(
    config: Mapping[str, Any],
    output: Path,
    *,
    environment: Mapping[str, str] | None = None,
    retrieved_at: str | None = None,
) -> list[dict[str, Any]]:
    """Capture configured sources and write one secret-free request manifest."""
    values = os.environ if environment is None else environment
    auth_variables = {"hf": "HF_TOKEN", "lumid": "LUMID_PAT"}
    records: list[dict[str, Any]] = []
    for target in config.get("targets", []):
        name = str(target["name"])
        group = str(target["group"])
        auth = str(target.get("auth", "none"))
        headers = {"Accept": str(target.get("accept", "application/json"))}
        variable = auth_variables.get(auth)
        token = values.get(variable, "") if variable is not None else ""
        if token:
            headers["Authorization"] = f"Bearer {token}"
        record = capture_http(
            str(target["url"]),
            output / group,
            name,
            request_headers=headers,
            timeout=float(target.get("timeout_seconds", 60.0)),
            retrieved_at=retrieved_at,
        )
        record.update({"auth_configured": bool(token), "group": group, "name": name})
        records.append(record)
    output.mkdir(parents=True, exist_ok=True)
    (output / "capture_manifest.json").write_text(
        json.dumps({"records": records}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return records
