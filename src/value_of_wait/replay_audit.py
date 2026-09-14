"""Fail-closed contracts for historical L2 replayability audits.

This module deliberately contains no model or routing logic.  It validates the
data needed before an execution-aware historical experiment can be defended.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable


CONDITION_ID_PATTERN = re.compile(r"^0x[0-9a-fA-F]{64}$")
ASSET_ID_PATTERN = re.compile(r"^[0-9]+$")
SPLIT_ORDER = ("train", "validation", "test")


class ReplayValidationError(ValueError):
    """Raised when a record cannot support fail-closed historical replay."""


def _decimal(value: Any, label: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ReplayValidationError(f"invalid {label}") from None
    if not parsed.is_finite():
        raise ReplayValidationError(f"invalid {label}")
    return parsed


def _decimal_text(value: Decimal) -> str:
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


def _parse_time(value: Any, label: str = "timestamp") -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ReplayValidationError(f"invalid {label}") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReplayValidationError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _time_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def normalize_market_tokens(row: dict[str, Any]) -> dict[str, str]:
    """Return a strict condition/YES/NO asset mapping from a market record."""
    condition_id = str(row.get("condition_id") or "").strip().lower()
    if not CONDITION_ID_PATTERN.fullmatch(condition_id):
        raise ReplayValidationError("invalid condition_id")

    outcomes = row.get("outcomes", row.get("tokens"))
    mapping: dict[str, str] = {}
    if isinstance(outcomes, list) and outcomes and all(isinstance(item, dict) for item in outcomes):
        for item in outcomes:
            label = str(item.get("name", item.get("outcome", item.get("label", "")))).strip().upper()
            asset = item.get("token_id", item.get("asset_id", item.get("id")))
            if label not in {"YES", "NO"} or label in mapping or asset is None:
                raise ReplayValidationError("ambiguous YES/NO outcome mapping")
            mapping[label] = str(asset).strip()
    elif isinstance(outcomes, list):
        assets = row.get("clob_token_ids", row.get("asset_ids"))
        if not isinstance(assets, list) or len(outcomes) != len(assets):
            raise ReplayValidationError("ambiguous YES/NO outcome mapping")
        for label_value, asset in zip(outcomes, assets):
            label = str(label_value).strip().upper()
            if label not in {"YES", "NO"} or label in mapping or asset is None:
                raise ReplayValidationError("ambiguous YES/NO outcome mapping")
            mapping[label] = str(asset).strip()
    else:
        raise ReplayValidationError("ambiguous YES/NO outcome mapping")

    if set(mapping) != {"YES", "NO"}:
        raise ReplayValidationError("ambiguous YES/NO outcome mapping")
    if not all(ASSET_ID_PATTERN.fullmatch(value) for value in mapping.values()):
        raise ReplayValidationError("asset_id must be a numeric string")
    if mapping["YES"] == mapping["NO"]:
        raise ReplayValidationError("YES and NO asset IDs must be distinct")
    return {
        "condition_id": condition_id,
        "source_market_id": str(row.get("market_id") or "").strip(),
        "yes_asset_id": mapping["YES"],
        "no_asset_id": mapping["NO"],
    }


def _levels(value: Any, side: str) -> list[dict[str, str]]:
    if value is None:
        value = []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            raise ReplayValidationError(f"invalid {side} level container") from None
    if isinstance(value, dict) and not {"price", "size"}.issubset(value):
        value = [[price, size] for price, size in value.items()]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ReplayValidationError(f"invalid {side} level container")

    parsed: list[dict[str, str]] = []
    prices: set[Decimal] = set()
    for item in value:
        if isinstance(item, dict):
            price_value, size_value = item.get("price"), item.get("size")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            price_value, size_value = item
        else:
            raise ReplayValidationError(f"invalid {side} level")
        price = _decimal(price_value, f"{side} level price")
        size = _decimal(size_value, f"{side} level size")
        if price < 0 or price > 1 or size <= 0:
            raise ReplayValidationError(f"invalid {side} level")
        if price in prices:
            raise ReplayValidationError(f"duplicate {side} level price")
        prices.add(price)
        parsed.append({"price": _decimal_text(price), "size": _decimal_text(size)})
    parsed.sort(key=lambda level: _decimal(level["price"], "level price"), reverse=side == "bid")
    return parsed


def parse_l2_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one full-book-shaped L2 row without assuming it is complete."""
    asset_id = str(row.get("asset_id", row.get("token_id", "")) or "").strip()
    if not ASSET_ID_PATTERN.fullmatch(asset_id):
        raise ReplayValidationError("invalid asset_id")
    condition_id = str(row.get("condition_id") or "").strip().lower()
    if condition_id and not CONDITION_ID_PATTERN.fullmatch(condition_id):
        raise ReplayValidationError("invalid condition_id")
    timestamp_value = row.get("snapshot_ts", row.get("timestamp", row.get("ts", row.get("created_at"))))
    timestamp = _parse_time(timestamp_value, "snapshot timestamp")
    return {
        "asset_id": asset_id,
        "condition_id": condition_id,
        "snapshot_ts": _time_text(timestamp),
        "bids": _levels(row.get("bids"), "bid"),
        "asks": _levels(row.get("asks"), "ask"),
        "tick_size": None if row.get("tick_size") is None else str(row.get("tick_size")),
        "min_order_size": None if row.get("min_order_size") is None else str(row.get("min_order_size")),
        "hash": None if row.get("hash") is None else str(row.get("hash")),
        "source": None if row.get("source") is None else str(row.get("source")),
    }


def validate_book(snapshot: dict[str, Any]) -> str:
    """Return a stable quality class for a normalized snapshot."""
    bids, asks = snapshot.get("bids") or [], snapshot.get("asks") or []
    if not bids or not asks:
        return "missing_side"
    best_bid = _decimal(bids[0]["price"], "best bid")
    best_ask = _decimal(asks[0]["price"], "best ask")
    if best_bid >= best_ask:
        return "crossed_book"
    return "valid"


def select_asof_snapshot(
    snapshots: Iterable[dict[str, Any]], decision_ts: str, *, max_age_seconds: float
) -> dict[str, Any]:
    """Select the latest snapshot at or before a decision and enforce freshness."""
    if max_age_seconds < 0:
        raise ReplayValidationError("max_age_seconds must be non-negative")
    decision = _parse_time(decision_ts, "decision timestamp")
    eligible: list[tuple[datetime, dict[str, Any]]] = []
    for snapshot in snapshots:
        stamp = _parse_time(snapshot.get("snapshot_ts"), "snapshot timestamp")
        if stamp <= decision:
            eligible.append((stamp, snapshot))
    if not eligible:
        raise ReplayValidationError("no snapshot at or before decision timestamp")
    latest_time = max(stamp for stamp, _ in eligible)
    latest = [snapshot for stamp, snapshot in eligible if stamp == latest_time]
    signatures = {hashlib.sha256(_canonical_json(snapshot)).hexdigest() for snapshot in latest}
    if len(signatures) != 1:
        raise ReplayValidationError("conflicting snapshots at the same timestamp")
    selected = latest[0]
    quality = validate_book(selected)
    if quality != "valid":
        raise ReplayValidationError(f"invalid as-of book: {quality}")
    age = (decision - latest_time).total_seconds()
    if age > max_age_seconds:
        raise ReplayValidationError(f"stale as-of book: age {age:.6f}s")
    return {"snapshot": selected, "age_seconds": age}


def walk_market_order(
    snapshot: dict[str, Any], *, side: str, quantity: Any, fee_bps: Any = "0"
) -> dict[str, Any]:
    """Walk visible depth for a marketable order; this is not a queue-fill model."""
    if validate_book(snapshot) != "valid":
        raise ReplayValidationError("cannot walk an invalid book")
    if side not in {"buy", "sell"}:
        raise ReplayValidationError("side must be buy or sell")
    requested = _decimal(quantity, "quantity")
    fee_rate = _decimal(fee_bps, "fee_bps") / Decimal("10000")
    if requested <= 0 or fee_rate < 0:
        raise ReplayValidationError("quantity and fee must be non-negative")
    levels = snapshot["asks"] if side == "buy" else snapshot["bids"]
    remaining, filled, notional, consumed = requested, Decimal("0"), Decimal("0"), 0
    for level in levels:
        if remaining <= 0:
            break
        available = _decimal(level["size"], "level size")
        take = min(remaining, available)
        if take <= 0:
            continue
        price = _decimal(level["price"], "level price")
        filled += take
        notional += take * price
        remaining -= take
        consumed += 1
    fee = notional * fee_rate
    average = notional / filled if filled else Decimal("0")
    cash = -(notional + fee) if side == "buy" else notional - fee
    return {
        "side": side,
        "requested_quantity": _decimal_text(requested),
        "filled_quantity": _decimal_text(filled),
        "full_fill": remaining == 0,
        "gross_notional": _decimal_text(notional),
        "average_price": _decimal_text(average),
        "fee": _decimal_text(fee),
        "net_cash_flow": _decimal_text(cash),
        "levels_consumed": consumed,
    }


def validate_split_integrity(rows: Iterable[dict[str, Any]], *, embargo_seconds: float) -> dict[str, Any]:
    """Reject market-family leakage and insufficient temporal embargoes."""
    if embargo_seconds < 0:
        raise ReplayValidationError("embargo_seconds must be non-negative")
    normalized = list(rows)
    families: dict[str, set[str]] = {}
    timestamps: dict[str, list[datetime]] = {}
    for row in normalized:
        family, split = str(row.get("family_id") or ""), str(row.get("split") or "")
        if not family or split not in SPLIT_ORDER:
            raise ReplayValidationError("invalid family or split")
        families.setdefault(family, set()).add(split)
        timestamps.setdefault(split, []).append(_parse_time(row.get("event_ts"), "event timestamp"))
    if any(len(splits) != 1 for splits in families.values()):
        raise ReplayValidationError("market family crosses data splits")
    present = [split for split in SPLIT_ORDER if timestamps.get(split)]
    for earlier, later in zip(present, present[1:]):
        gap = (min(timestamps[later]) - max(timestamps[earlier])).total_seconds()
        if gap < embargo_seconds:
            raise ReplayValidationError("temporal embargo is violated")
    return {"families": len(families), "rows": len(normalized), "splits": present}


def build_overlap_funnel(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the strict nested event--market--L2 funnel."""
    current = list(records)
    stages = [("candidate_external_events", None)]
    stages.extend(
        [
            ("point_in_time_active_markets", "pit_active_verified"),
            ("historical_l2_window", "historical_l2_window"),
            ("valid_entry_deep_exit_books", "valid_books"),
            ("verified_outcomes", "verified_outcome"),
        ]
    )
    output: list[dict[str, Any]] = []
    for index, (name, field) in enumerate(stages, start=1):
        if field is not None:
            current = [row for row in current if row.get(field) is True]
        families = {str(row.get("family_id") or "") for row in current if row.get("family_id")}
        output.append({"stage": index, "name": name, "rows": len(current), "independent_families": len(families)})
    family_count = output[-1]["independent_families"]
    output.append({"stage": 6, "name": "independent_event_families", "rows": family_count, "independent_families": family_count})
    return output


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({field for row in rows for field in row})
    ordered = sorted(rows, key=lambda row: _canonical_json(row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in ordered:
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            row_count = sum(1 for _ in csv.DictReader(handle))
    else:
        row_count = 1
    return {"path": path.name, "bytes": len(data), "rows": row_count, "sha256": hashlib.sha256(data).hexdigest()}


def write_audit_release(
    output: Path,
    *,
    summary: dict[str, Any],
    funnel: list[dict[str, Any]],
    l2_coverage: list[dict[str, Any]],
) -> None:
    """Write deterministic aggregate evidence and its reconstruction manifest."""
    output.mkdir(parents=True, exist_ok=True)
    summary_path = output / "audit_summary.json"
    funnel_path = output / "funnel.csv"
    coverage_path = output / "l2_coverage.csv"
    _write_json(summary_path, summary)
    _write_csv(funnel_path, funnel)
    _write_csv(coverage_path, l2_coverage)
    artifacts = [_file_record(path) for path in (summary_path, funnel_path, coverage_path)]
    _write_json(output / "reconstruction_manifest.json", {"schema_version": "replay-audit-manifest-v1", "artifacts": artifacts})
