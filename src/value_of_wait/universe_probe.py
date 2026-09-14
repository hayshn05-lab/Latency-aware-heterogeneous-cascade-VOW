"""Broad market-level REST coverage probe for trades and both L2 assets."""
from __future__ import annotations

from datetime import timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .client import FindataClient, token_from_environment
from .dataset_builder import _SourceStore, _artifact, _digest, _rows, _time_text, _write_csv, _write_json
from .replay_audit import ReplayValidationError, normalize_market_tokens, parse_l2_snapshot, validate_book
from .starter_dataset import _canonical_bytes, _parse_utc


SEARCH_ENDPOINT = "/prediction-markets/markets/search"
DETAIL_ENDPOINT = "/prediction-markets/markets/polymarket/{condition_id}"
TRADE_ENDPOINT = "/prediction-markets/trades/polymarket/{condition_id}"
BOOK_ENDPOINT = "/prediction-markets/orderbook/polymarket/{asset_id}"


def _source_time(row: dict[str, Any], *names: str) -> str | None:
    for name in names:
        if row.get(name) is not None:
            return str(row[name])
    return None


def probe_market_universe(
    config: dict[str, Any],
    release_dir: Path,
    *,
    offline: bool,
    environment: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Probe top search results without treating provider-wide counts as coverage."""
    required = ("dataset_version", "base_url", "universe_raw_dir", "sample_start", "sample_end", "market_search_limit", "strata")
    missing = [name for name in required if name not in config]
    if missing:
        raise ReplayValidationError("missing universe-probe fields: " + ", ".join(missing))
    if not offline and client is None:
        client = FindataClient(str(config["base_url"]), token_from_environment(environment))
    release_dir = Path(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)
    store = _SourceStore(Path(config["universe_raw_dir"]), offline=offline, client=client)
    sample_start, sample_end = _parse_utc(config["sample_start"]), _parse_utc(config["sample_end"])
    rows_out: list[dict[str, Any]] = []

    for stratum in sorted(config["strata"], key=lambda item: (str(item.get("name")), str(item.get("query")))):
        name, query = str(stratum["name"]), str(stratum["query"])
        params = {
            "q": query,
            "venue": "polymarket",
            "status": str(stratum.get("status", "closed")),
            "limit": int(config["market_search_limit"]),
            "offset": 0,
        }
        markets = _rows(store.fetch(SEARCH_ENDPOINT, params))
        for rank, market in enumerate(markets, start=1):
            condition_id = str(market.get("condition_id", market.get("market_id", ""))).lower()
            record: dict[str, Any] = {
                "stratum": name,
                "query": query,
                "search_rank": rank,
                "condition_id": condition_id,
                "title": str(market.get("title", market.get("question", ""))),
                "schedule_valid": False,
                "token_mapping_valid": False,
                "trade_any": False,
                "latest_trade_ts": None,
                "yes_l2_any": False,
                "yes_latest_snapshot_ts": None,
                "yes_book_quality": None,
                "no_l2_any": False,
                "no_latest_snapshot_ts": None,
                "no_book_quality": None,
                "both_asset_l2": False,
                "reason": None,
            }
            if not condition_id.startswith("0x") or len(condition_id) != 66:
                record["reason"] = "invalid condition_id"
                rows_out.append(record)
                continue
            detail_payload = store.fetch(DETAIL_ENDPOINT.format(condition_id=condition_id), {})
            detail_rows = _rows(detail_payload)
            detail = detail_rows[0] if detail_rows else (detail_payload if isinstance(detail_payload, dict) else {})
            record["title"] = str(detail.get("question", record["title"]))
            try:
                tokens = normalize_market_tokens(detail)
            except ReplayValidationError as error:
                record["reason"] = str(error)
                rows_out.append(record)
                continue
            record["token_mapping_valid"] = True
            try:
                start = max(sample_start, _parse_utc(detail.get("start_date", market.get("start_date"))))
                end = min(sample_end, _parse_utc(detail.get("end_date", market.get("end_date"))))
            except ReplayValidationError:
                record["reason"] = "missing or invalid market schedule"
                rows_out.append(record)
                continue
            if start >= end:
                record["reason"] = "no valid schedule overlap"
                rows_out.append(record)
                continue
            record["schedule_valid"] = True
            window = {"from": _time_text(start), "to": _time_text(end), "limit": 1}
            trades = _rows(store.fetch(TRADE_ENDPOINT.format(condition_id=condition_id), window))
            record["trade_any"] = bool(trades)
            if trades:
                record["latest_trade_ts"] = _source_time(trades[0], "ts", "timestamp", "created_at")

            for outcome, asset_id in (("yes", tokens["yes_asset_id"]), ("no", tokens["no_asset_id"])):
                books = _rows(store.fetch(BOOK_ENDPOINT.format(asset_id=asset_id), window))
                record[f"{outcome}_l2_any"] = bool(books)
                if not books:
                    continue
                try:
                    normalized = parse_l2_snapshot(books[0])
                    if normalized["asset_id"] != asset_id:
                        raise ReplayValidationError("book asset mismatch")
                except ReplayValidationError as error:
                    record[f"{outcome}_book_quality"] = "parse_error"
                    record["reason"] = str(error)
                    continue
                record[f"{outcome}_latest_snapshot_ts"] = normalized["snapshot_ts"]
                record[f"{outcome}_book_quality"] = validate_book(normalized)
            record["both_asset_l2"] = bool(record["yes_l2_any"] and record["no_l2_any"])
            rows_out.append(record)

    fields = [
        "stratum", "query", "search_rank", "condition_id", "title", "schedule_valid", "token_mapping_valid",
        "trade_any", "latest_trade_ts", "yes_l2_any", "yes_latest_snapshot_ts", "yes_book_quality",
        "no_l2_any", "no_latest_snapshot_ts", "no_book_quality", "both_asset_l2", "reason",
    ]
    csv_path = release_dir / "market_universe_probe.csv"
    _write_csv(csv_path, rows_out, fields)
    by_stratum = []
    for name in sorted({row["stratum"] for row in rows_out}):
        group = [row for row in rows_out if row["stratum"] == name]
        by_stratum.append({
            "stratum": name,
            "markets": len(group),
            "valid_schedules": sum(row["schedule_valid"] for row in group),
            "any_trade": sum(row["trade_any"] for row in group),
            "yes_l2": sum(row["yes_l2_any"] for row in group),
            "no_l2": sum(row["no_l2_any"] for row in group),
            "both_asset_l2": sum(row["both_asset_l2"] for row in group),
        })
    summary = {
        "dataset_version": str(config["dataset_version"]),
        "markets_scanned": len(rows_out),
        "markets_with_valid_schedule_and_mapping": sum(row["schedule_valid"] and row["token_mapping_valid"] for row in rows_out),
        "markets_with_any_trade": sum(row["trade_any"] for row in rows_out),
        "markets_with_yes_l2": sum(row["yes_l2_any"] for row in rows_out),
        "markets_with_no_l2": sum(row["no_l2_any"] for row in rows_out),
        "markets_with_both_asset_l2": sum(row["both_asset_l2"] for row in rows_out),
        "by_stratum": by_stratum,
    }
    summary_path = release_dir / "universe_probe_summary.json"
    _write_json(summary_path, summary)
    manifest = {
        "schema_version": "market-universe-probe-v1",
        "dataset_version": str(config["dataset_version"]),
        "config_sha256": _digest(config),
        "raw_release_required": True,
        "source_requests": sorted(store.requests.values(), key=_canonical_bytes),
        "artifacts": [_artifact(csv_path), _artifact(summary_path)],
    }
    _write_json(release_dir / "universe_probe_manifest.json", manifest)
    return summary
