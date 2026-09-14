"""Versioned starter-dataset construction for the historical replay gate."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from statistics import median
from typing import Any, Iterable

from .replay_audit import ReplayValidationError, validate_book


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ReplayValidationError("invalid timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplayValidationError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def deduplicate_full_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove only byte-canonical duplicate rows, never duplicate IDs alone."""
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        digest = hashlib.sha256(_canonical_bytes(row)).hexdigest()
        unique.setdefault(digest, row)
    return sorted(unique.values(), key=_canonical_bytes)


def point_in_time_eligibility(event_ts: str, market: dict[str, Any]) -> dict[str, Any]:
    """Require explicit historical index and open-state evidence."""
    event = _parse_utc(event_ts)
    start_value, end_value = market.get("start_date"), market.get("end_date")
    if start_value is None or end_value is None:
        return {"eligible": False, "reason": "market schedule unavailable"}
    if not (_parse_utc(start_value) <= event <= _parse_utc(end_value)):
        return {"eligible": False, "reason": "event outside market schedule"}
    indexed_value = market.get("indexed_ts")
    if indexed_value is None:
        return {"eligible": False, "reason": "historical index timestamp unavailable"}
    if _parse_utc(indexed_value) > event:
        return {"eligible": False, "reason": "market indexed after event"}
    if market.get("historical_open") is not True:
        return {"eligible": False, "reason": "historical open state not verified"}
    return {"eligible": True, "reason": "verified active/open/indexed at event time"}


def summarize_snapshot_series(snapshots: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Summarize observed full-book rows without filling temporal gaps."""
    rows = sorted(list(snapshots), key=lambda row: _parse_utc(row.get("snapshot_ts")))
    if not rows:
        return {
            "snapshot_count": 0,
            "first_snapshot_ts": None,
            "last_snapshot_ts": None,
            "median_gap_seconds": None,
            "p95_gap_seconds": None,
            "max_gap_seconds": None,
            "valid_book_fraction": None,
        }
    times = [_parse_utc(row["snapshot_ts"]) for row in rows]
    gaps = [(later - earlier).total_seconds() for earlier, later in zip(times, times[1:])]
    ordered_gaps = sorted(gaps)
    p95 = ordered_gaps[max(0, math.ceil(0.95 * len(ordered_gaps)) - 1)] if ordered_gaps else None
    return {
        "snapshot_count": len(rows),
        "first_snapshot_ts": rows[0]["snapshot_ts"],
        "last_snapshot_ts": rows[-1]["snapshot_ts"],
        "median_gap_seconds": float(median(ordered_gaps)) if ordered_gaps else None,
        "p95_gap_seconds": float(p95) if p95 is not None else None,
        "max_gap_seconds": float(max(ordered_gaps)) if ordered_gaps else None,
        "valid_book_fraction": sum(validate_book(row) == "valid" for row in rows) / len(rows),
    }


def build_starter_dataset(config, release_dir, output_dir, *, offline, environment=None, client=None):
    """Build or reconstruct the versioned audit starter release."""
    from .dataset_builder import build_starter_dataset as implementation
    return implementation(config, release_dir, output_dir, offline=offline, environment=environment, client=client)
