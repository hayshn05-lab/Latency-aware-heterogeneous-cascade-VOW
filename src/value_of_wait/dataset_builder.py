"""Findata REST starter-release builder for the historical replayability gate."""
from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from .client import FindataClient, token_from_environment
from .parsing import parse_trades
from .pipeline import load_cache_entry, save_cache_entry
from .replay_audit import (
    ReplayValidationError,
    build_overlap_funnel,
    normalize_market_tokens,
    parse_l2_snapshot,
    select_asof_snapshot,
    validate_book,
    write_audit_release,
)
from .starter_dataset import (
    _canonical_bytes,
    _parse_utc,
    deduplicate_full_rows,
    point_in_time_eligibility,
    summarize_snapshot_series,
)


DEFAULT_ENDPOINTS = {
    "market_search": "/prediction-markets/markets/search",
    "market_detail": "/prediction-markets/markets/polymarket/{condition_id}",
    "tweet_search": "/kols/tweets/search",
    "trades": "/prediction-markets/trades/polymarket/{condition_id}",
    "orderbook": "/prediction-markets/orderbook/polymarket/{asset_id}",
}
CATALOG_ENDPOINTS = (
    "/catalog/tables/prediction_markets/polymarket_trades",
    "/catalog/tables/prediction_markets/polymarket_trades/schema.json",
    "/catalog/tables/prediction_markets/polymarket_orderbook_snapshots",
    "/catalog/tables/prediction_markets/polymarket_orderbook_snapshots/schema.json",
)


def _time_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "results", "markets", "tweets", "trades", "snapshots", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _rows(value)
            if nested:
                return nested
    if any(key in payload for key in ("condition_id", "asset_id", "trade_id", "tweet_id", "table", "$schema")):
        return [payload]
    return []


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


class _SourceStore:
    def __init__(self, raw_dir: Path, *, offline: bool, client: Any | None) -> None:
        self.raw_dir = raw_dir
        self.offline = offline
        self.client = client
        self.requests: dict[str, dict[str, Any]] = {}

    def fetch(self, endpoint: str, params: dict[str, Any]) -> Any:
        clean_params = dict(sorted(params.items()))
        if self.offline:
            payload, metadata = load_cache_entry(self.raw_dir, endpoint, clean_params)
        else:
            if self.client is None:
                raise RuntimeError("online source client is unavailable")
            payload = self.client.get_json(endpoint, clean_params)
            path = save_cache_entry(self.raw_dir, endpoint, clean_params, payload)
            metadata = {"retrieved_at": json.loads(path.read_text(encoding="utf-8"))["retrieved_at"]}
        request_key = _digest({"endpoint": endpoint, "params": clean_params})
        self.requests[request_key] = {
            "endpoint": endpoint,
            "params": clean_params,
            "retrieved_at": metadata.get("retrieved_at"),
            "row_count": len(_rows(payload)),
            "response_sha256": _digest(payload),
        }
        return payload


def _bounded_window(
    store: _SourceStore,
    endpoint: str,
    start: datetime,
    end: datetime,
    limit: int,
    *,
    depth: int = 0,
) -> tuple[list[dict[str, Any]], bool]:
    params = {"from": _time_text(start), "to": _time_text(end), "limit": limit}
    rows = _rows(store.fetch(endpoint, params))
    if len(rows) < limit:
        return deduplicate_full_rows(rows), False
    if end <= start or (end - start).total_seconds() <= 1 or depth >= 24:
        return deduplicate_full_rows(rows), True
    midpoint = start + (end - start) / 2
    left, left_unresolved = _bounded_window(store, endpoint, start, midpoint, limit, depth=depth + 1)
    right, right_unresolved = _bounded_window(store, endpoint, midpoint, end, limit, depth=depth + 1)
    return deduplicate_full_rows(left + right), left_unresolved or right_unresolved


def _family_id(slug: str, title: str) -> str:
    source = (slug or title).casefold()
    source = re.sub(r"\d+(?:\.\d+)?", "{n}", source)
    source = re.sub(r"[^a-z{}]+", "-", source).strip("-")
    return "heuristic-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def _outcome_verified(detail: dict[str, Any]) -> bool:
    outcomes, prices = detail.get("outcomes"), detail.get("outcome_prices")
    if detail.get("closed") is not True or not isinstance(outcomes, list) or not isinstance(prices, list) or len(outcomes) != len(prices):
        return False
    mapping: dict[str, str] = {}
    for outcome, price in zip(outcomes, prices):
        label = str(outcome.get("name", "") if isinstance(outcome, dict) else outcome).strip().upper()
        if label in {"YES", "NO"}:
            mapping[label] = str(price)
    try:
        values = {float(mapping["YES"]), float(mapping["NO"])}
    except (KeyError, TypeError, ValueError):
        return False
    return values == {0.0, 1.0}


def _timestamp_precision(values: Iterable[Any]) -> str:
    digits: list[int] = []
    nonzero = False
    for value in values:
        match = re.search(r"\.(\d+)(?:Z|[+-]\d\d:\d\d)?$", str(value))
        fraction = match.group(1) if match else ""
        digits.append(len(fraction))
        nonzero = nonzero or bool(fraction and int(fraction) != 0)
    if digits and min(digits) >= 3 and nonzero:
        return "milliseconds-or-finer"
    if digits and min(digits) > 0 and nonzero:
        return "fractional-seconds"
    return "seconds"


def event_author_allowed(author: Any, excluded_authors: Iterable[Any]) -> bool:
    """Return whether an event author is not an exact case-insensitive exclusion."""
    excluded = {str(value).casefold() for value in excluded_authors}
    return str(author).casefold() not in excluded


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ordered = sorted(rows, key=_canonical_bytes)
    text = "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in ordered)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        for row in sorted(rows, key=_canonical_bytes):
            writer.writerow({field: "" if row.get(field) is None else row.get(field) for field in fields})


def _artifact(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    rows = None
    if path.suffix == ".csv":
        with path.open(encoding="utf-8", newline="") as handle:
            rows = sum(1 for _ in csv.DictReader(handle))
    return {"path": path.name, "bytes": len(data), "rows": rows, "sha256": hashlib.sha256(data).hexdigest()}


def _asof_row(
    pair_id: str,
    outcome: str,
    asset_id: str,
    snapshots: list[dict[str, Any]],
    decision: datetime,
    offset: int,
    max_age: float,
) -> dict[str, Any]:
    base = {
        "pair_id": pair_id,
        "outcome": outcome,
        "asset_id": asset_id,
        "offset_seconds": offset,
        "decision_ts": _time_text(decision),
        "status": "missing",
        "snapshot_ts": None,
        "age_seconds": None,
        "book_quality": None,
    }
    eligible = [row for row in snapshots if _parse_utc(row["snapshot_ts"]) <= decision]
    if eligible:
        latest = max(eligible, key=lambda row: (_parse_utc(row["snapshot_ts"]), _canonical_bytes(row)))
        base["snapshot_ts"] = latest["snapshot_ts"]
        base["age_seconds"] = (decision - _parse_utc(latest["snapshot_ts"])).total_seconds()
        base["book_quality"] = validate_book(latest)
    try:
        selected = select_asof_snapshot(snapshots, _time_text(decision), max_age_seconds=max_age)
    except ReplayValidationError as error:
        message = str(error)
        if "stale" in message:
            base["status"] = "stale"
        elif "invalid as-of" in message:
            base["status"] = "invalid_book"
        else:
            base["status"] = "missing"
    else:
        base["status"] = "valid"
        base["snapshot_ts"] = selected["snapshot"]["snapshot_ts"]
        base["age_seconds"] = selected["age_seconds"]
        base["book_quality"] = "valid"
    return base


def _release_readme(dataset_version: str) -> str:
    return f"""# {dataset_version}

This is a versioned **audit starter release**, not a model-ready gold dataset.
Tweet text and immutable API responses remain in the ignored raw/interim release;
this committed directory contains identifiers, hashes, provenance, exclusions,
and replayability measurements.  Shared-query retrieval is not a verified
event--market semantic label.  Missing, stale, crossed, or one-sided books are
never converted to zero movement or an executable state.

Reconstruction requires the matching `data/raw/findata/{dataset_version}`
archive.  A fresh clone without that source release is not source-reproducible.
"""


def build_starter_dataset(
    config: dict[str, Any],
    release_dir: Path,
    output_dir: Path,
    *,
    offline: bool,
    environment: dict[str, str] | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Build the broad audit sample and deterministic replayability evidence."""
    required = (
        "dataset_version", "base_url", "raw_dir", "interim_dir", "sample_start", "sample_end",
        "market_search_limit", "markets_per_stratum", "tweet_search_limit", "events_per_market",
        "rest_limit", "window_before_seconds", "window_after_seconds", "required_book_offsets_seconds",
        "max_book_age_seconds", "strata",
    )
    missing = [name for name in required if name not in config]
    if missing:
        raise ReplayValidationError("missing configuration fields: " + ", ".join(missing))
    if not offline and client is None:
        client = FindataClient(str(config["base_url"]), token_from_environment(environment))

    raw_dir, interim_dir = Path(config["raw_dir"]), Path(config["interim_dir"])
    release_dir, output_dir = Path(release_dir), Path(output_dir)
    for directory in (raw_dir, interim_dir, release_dir, output_dir):
        directory.mkdir(parents=True, exist_ok=True)
    store = _SourceStore(raw_dir, offline=offline, client=client)
    endpoints = DEFAULT_ENDPOINTS | config.get("endpoints", {})
    for endpoint in CATALOG_ENDPOINTS:
        store.fetch(endpoint, {})

    sample_start, sample_end = _parse_utc(config["sample_start"]), _parse_utc(config["sample_end"])
    market_records: dict[str, dict[str, Any]] = {}
    details: dict[str, dict[str, Any]] = {}
    token_maps: dict[str, dict[str, str]] = {}
    events: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []

    for stratum in sorted(config["strata"], key=lambda item: (str(item.get("name")), str(item.get("query")))):
        stratum_name, query = str(stratum["name"]), str(stratum["query"])
        search_params = {
            "q": query,
            "venue": "polymarket",
            "status": str(stratum.get("status", "closed")),
            "limit": int(config["market_search_limit"]),
            "offset": 0,
        }
        search_rows = _rows(store.fetch(endpoints["market_search"], search_params))
        accepted_markets = 0
        for search_row in search_rows:
            if accepted_markets >= int(config["markets_per_stratum"]):
                break
            condition_id = str(search_row.get("condition_id", search_row.get("market_id", ""))).lower()
            if not re.fullmatch(r"0x[0-9a-f]{64}", condition_id):
                exclusions.append({"stage": "market", "stratum": stratum_name, "source_id": condition_id, "reason": "invalid condition_id"})
                continue
            detail_payload = store.fetch(endpoints["market_detail"].format(condition_id=condition_id), {})
            detail_rows = _rows(detail_payload)
            detail = detail_rows[0] if detail_rows else (detail_payload if isinstance(detail_payload, dict) else {})
            try:
                tokens = normalize_market_tokens(detail)
            except ReplayValidationError as error:
                exclusions.append({"stage": "market", "stratum": stratum_name, "source_id": condition_id, "reason": str(error)})
                continue
            try:
                start = max(sample_start, _parse_utc(detail.get("start_date", search_row.get("start_date"))))
                end = min(sample_end, _parse_utc(detail.get("end_date", search_row.get("end_date"))))
            except ReplayValidationError:
                exclusions.append({"stage": "market", "stratum": stratum_name, "source_id": condition_id, "reason": "missing or invalid market schedule"})
                continue
            if start >= end:
                exclusions.append({"stage": "market", "stratum": stratum_name, "source_id": condition_id, "reason": "no overlap with configured sample window"})
                continue
            tweet_params = {"q": query, "since": _time_text(start), "until": _time_text(end), "limit": int(config["tweet_search_limit"])}
            tweet_rows = _rows(store.fetch(endpoints["tweet_search"], tweet_params))
            usable_tweets = []
            for tweet in tweet_rows:
                event_id = str(tweet.get("tweet_id", tweet.get("id", "")))
                author = str(tweet.get("kol_username", tweet.get("author_username", "")))
                event_ts = tweet.get("created_at", tweet.get("timestamp"))
                if not event_author_allowed(author, config.get("excluded_event_authors", [])):
                    exclusions.append({"stage": "event", "stratum": stratum_name, "source_id": event_id, "reason": "endogenous market/venue account is excluded"})
                    continue
                try:
                    event_time = _parse_utc(event_ts)
                except ReplayValidationError:
                    exclusions.append({"stage": "event", "stratum": stratum_name, "source_id": event_id, "reason": "missing or invalid event timestamp"})
                    continue
                if not (start <= event_time <= end):
                    exclusions.append({"stage": "event", "stratum": stratum_name, "source_id": event_id, "reason": "event outside market schedule"})
                    continue
                usable_tweets.append((event_time, event_id, author, tweet))
            usable_tweets.sort(key=lambda item: (item[0], item[1]), reverse=True)
            usable_tweets = usable_tweets[: int(config["events_per_market"])]
            if not usable_tweets:
                exclusions.append({"stage": "event", "stratum": stratum_name, "source_id": condition_id, "reason": "no in-window tweet candidate returned"})
                continue

            accepted_markets += 1
            details[condition_id], token_maps[condition_id] = detail, tokens
            title = str(detail.get("question", search_row.get("title", "")))
            slug = str(detail.get("slug", search_row.get("slug", "")))
            family_id = _family_id(slug, title)
            market_records[condition_id] = {
                "condition_id": condition_id,
                "source_market_id": tokens["source_market_id"],
                "stratum": stratum_name,
                "title": title,
                "slug": slug,
                "start_date": str(detail.get("start_date", search_row.get("start_date", ""))),
                "end_date": str(detail.get("end_date", search_row.get("end_date", ""))),
                "closed_now": detail.get("closed"),
                "active_now": detail.get("active"),
                "yes_asset_id": tokens["yes_asset_id"],
                "no_asset_id": tokens["no_asset_id"],
                "outcome_verified": _outcome_verified(detail),
                "family_id": family_id,
                "family_id_verified": False,
            }
            for event_time, event_id, author, tweet in usable_tweets:
                event_record = {
                    "event_id": event_id,
                    "tweet_id": event_id,
                    "event_ts": _time_text(event_time),
                    "stratum": stratum_name,
                    "author": author,
                    "text_sha256": hashlib.sha256(str(tweet.get("text", "")).encode("utf-8")).hexdigest(),
                    "source_query": query,
                }
                events.append(event_record)
                pair_id = hashlib.sha256(f'{config["dataset_version"]}|{stratum_name}|{event_id}|{condition_id}'.encode("utf-8")).hexdigest()[:24]
                candidates.append({
                    "pair_id": pair_id,
                    "event_id": event_id,
                    "event_ts": event_record["event_ts"],
                    "condition_id": condition_id,
                    "stratum": stratum_name,
                    "family_id": family_id,
                    "source_query": query,
                })

    trade_coverage: list[dict[str, Any]] = []
    l2_coverage: list[dict[str, Any]] = []
    asof_rows: list[dict[str, Any]] = []
    normalized_trades: list[dict[str, Any]] = []
    normalized_books: list[dict[str, Any]] = []
    pair_rows: list[dict[str, Any]] = []
    before = int(config["window_before_seconds"])
    after = int(config["window_after_seconds"])
    rest_limit = int(config["rest_limit"])
    offsets = sorted({int(value) for value in config["required_book_offsets_seconds"]})
    max_age = float(config["max_book_age_seconds"])

    for candidate in sorted(candidates, key=_canonical_bytes):
        pair_id, condition_id = candidate["pair_id"], candidate["condition_id"]
        event_time = _parse_utc(candidate["event_ts"])
        window_start, window_end = event_time - timedelta(seconds=before), event_time + timedelta(seconds=after)
        tokens = token_maps[condition_id]
        trade_endpoint = endpoints["trades"].format(condition_id=condition_id)
        trade_rows, trade_truncated = _bounded_window(store, trade_endpoint, window_start, window_end, rest_limit)
        parsed_trades = parse_trades(trade_rows, {"YES": tokens["yes_asset_id"], "NO": tokens["no_asset_id"]})
        for row in parsed_trades:
            normalized_trades.append({"pair_id": pair_id, "condition_id": condition_id, **row})
        trade_times = [str(row.get("timestamp")) for row in parsed_trades]
        trade_coverage.append({
            "pair_id": pair_id,
            "condition_id": condition_id,
            "raw_trade_rows": len(trade_rows),
            "normalized_trade_rows": len(parsed_trades),
            "potentially_truncated": trade_truncated,
            "first_trade_ts": min(trade_times) if trade_times else None,
            "last_trade_ts": max(trade_times) if trade_times else None,
            "timestamp_precision": _timestamp_precision(trade_times),
        })

        asset_has_window: list[bool] = []
        asset_valid: list[bool] = []
        for outcome, asset_id in (("YES", tokens["yes_asset_id"]), ("NO", tokens["no_asset_id"])):
            book_endpoint = endpoints["orderbook"].format(asset_id=asset_id)
            raw_books, book_truncated = _bounded_window(store, book_endpoint, window_start, window_end, rest_limit)
            parsed_books: list[dict[str, Any]] = []
            parse_errors = 0
            for raw_book in raw_books:
                try:
                    book = parse_l2_snapshot(raw_book)
                    if book["asset_id"] != asset_id or (book["condition_id"] and book["condition_id"] != condition_id):
                        raise ReplayValidationError("book identifier mismatch")
                except ReplayValidationError as error:
                    parse_errors += 1
                    exclusions.append({"stage": "l2", "stratum": candidate["stratum"], "source_id": pair_id + ":" + asset_id, "reason": str(error)})
                    continue
                parsed_books.append(book)
                normalized_books.append({"pair_id": pair_id, "outcome": outcome, **book})
            parsed_books = deduplicate_full_rows(parsed_books)
            metrics = summarize_snapshot_series(parsed_books)
            coverage_row = {
                "pair_id": pair_id,
                "condition_id": condition_id,
                "outcome": outcome,
                "asset_id": asset_id,
                "raw_snapshot_rows": len(raw_books),
                "parsed_snapshot_rows": len(parsed_books),
                "parse_errors": parse_errors,
                "potentially_truncated": book_truncated,
                **metrics,
                "timestamp_precision": _timestamp_precision([row["snapshot_ts"] for row in parsed_books]),
            }
            l2_coverage.append(coverage_row)
            asset_has_window.append(bool(parsed_books) and not book_truncated)
            asset_asof = []
            for offset in offsets:
                audit = _asof_row(pair_id, outcome, asset_id, parsed_books, event_time + timedelta(seconds=offset), offset, max_age)
                asof_rows.append(audit)
                asset_asof.append(audit)
            asset_valid.append(bool(asset_asof) and all(row["status"] == "valid" for row in asset_asof))

        detail = details[condition_id]
        pit = point_in_time_eligibility(candidate["event_ts"], detail)
        semantic_verified = bool(detail.get("semantic_alignment_verified") is True)
        strict_pit = pit["eligible"] and semantic_verified
        pair_rows.append({
            **candidate,
            "semantic_alignment_verified": semantic_verified,
            "semantic_reason": "shared retrieval query only; no human/EventX gold label" if not semantic_verified else "verified",
            "calendar_overlap": _parse_utc(detail["start_date"]) <= event_time <= _parse_utc(detail["end_date"]),
            "pit_active_verified": strict_pit,
            "pit_reason": pit["reason"] if not pit["eligible"] else ("semantic alignment unverified" if not semantic_verified else pit["reason"]),
            "historical_l2_window": len(asset_has_window) == 2 and all(asset_has_window),
            "valid_books": len(asset_valid) == 2 and all(asset_valid),
            "verified_outcome": market_records[condition_id]["outcome_verified"],
        })

    funnel = build_overlap_funnel(pair_rows)
    valid_pairs = sum(row["valid_books"] for row in pair_rows)
    trade_pairs = sum(row["normalized_trade_rows"] > 0 and not row["potentially_truncated"] for row in trade_coverage)
    strict_families = int(funnel[-1]["independent_families"])
    if strict_families > 0 and valid_pairs > 0:
        tier = "H2"
    elif valid_pairs > 0:
        tier = "H1"
    elif trade_pairs > 0:
        tier = "H0"
    else:
        tier = "D0"
    event_precision = _timestamp_precision([row["event_ts"] for row in events])
    trade_precision = _timestamp_precision([row.get("timestamp") for row in normalized_trades])
    summary = {
        "dataset_version": str(config["dataset_version"]),
        "evidence_tier": tier,
        "historical_execution_replayable": tier == "H2",
        "strict_effective_family_count": strict_families,
        "candidate_pairs": len(pair_rows),
        "candidate_events": len({row["event_id"] for row in pair_rows}),
        "candidate_markets": len({row["condition_id"] for row in pair_rows}),
        "diagnostic_pairs_with_any_l2": sum(row["historical_l2_window"] for row in pair_rows),
        "diagnostic_pairs_with_valid_books": valid_pairs,
        "pairs_with_nontruncated_trades": trade_pairs,
        "event_timestamp_precision": event_precision,
        "trade_timestamp_precision": trade_precision,
        "subsecond_identifiable": event_precision != "seconds" and trade_precision != "seconds",
        "primary_claim": "historical execution-aware backtesting" if tier == "H2" else "historical execution replay gate not passed",
    }

    interim_files = {
        "events.jsonl": events,
        "markets.jsonl": list(market_records.values()),
        "event_market_candidates.jsonl": pair_rows,
        "trades.jsonl": normalized_trades,
        "l2_snapshots.jsonl": normalized_books,
        "l2_asof.jsonl": asof_rows,
    }
    for name, rows in interim_files.items():
        _write_jsonl(interim_dir / name, rows)

    release_fields = {
        "candidate_events.csv": ["event_id", "tweet_id", "event_ts", "stratum", "author", "text_sha256", "source_query"],
        "markets.csv": ["condition_id", "source_market_id", "stratum", "title", "slug", "start_date", "end_date", "closed_now", "active_now", "yes_asset_id", "no_asset_id", "outcome_verified", "family_id", "family_id_verified"],
        "event_market_candidates.csv": ["pair_id", "event_id", "event_ts", "condition_id", "stratum", "family_id", "source_query", "semantic_alignment_verified", "semantic_reason", "calendar_overlap", "pit_active_verified", "pit_reason", "historical_l2_window", "valid_books", "verified_outcome"],
        "trade_coverage.csv": ["pair_id", "condition_id", "raw_trade_rows", "normalized_trade_rows", "potentially_truncated", "first_trade_ts", "last_trade_ts", "timestamp_precision"],
        "l2_coverage.csv": ["pair_id", "condition_id", "outcome", "asset_id", "raw_snapshot_rows", "parsed_snapshot_rows", "parse_errors", "potentially_truncated", "snapshot_count", "first_snapshot_ts", "last_snapshot_ts", "median_gap_seconds", "p95_gap_seconds", "max_gap_seconds", "valid_book_fraction", "timestamp_precision"],
        "l2_asof.csv": ["pair_id", "outcome", "asset_id", "offset_seconds", "decision_ts", "status", "snapshot_ts", "age_seconds", "book_quality"],
        "exclusions.csv": ["stage", "stratum", "source_id", "reason"],
        "funnel.csv": ["stage", "name", "rows", "independent_families"],
    }
    release_rows = {
        "candidate_events.csv": events,
        "markets.csv": list(market_records.values()),
        "event_market_candidates.csv": pair_rows,
        "trade_coverage.csv": trade_coverage,
        "l2_coverage.csv": l2_coverage,
        "l2_asof.csv": asof_rows,
        "exclusions.csv": exclusions,
        "funnel.csv": funnel,
    }
    for name, fields in release_fields.items():
        _write_csv(release_dir / name, release_rows[name], fields)
    (release_dir / "README.md").write_text(_release_readme(str(config["dataset_version"])), encoding="utf-8")
    pre_manifest_paths = [
        release_dir / name
        for name in (
            "README.md",
            "candidate_events.csv",
            "event_market_candidates.csv",
            "exclusions.csv",
            "funnel.csv",
            "l2_asof.csv",
            "l2_coverage.csv",
            "markets.csv",
            "trade_coverage.csv",
        )
    ]
    data_manifest = {
        "dataset_version": str(config["dataset_version"]),
        "schema_version": "starter-replay-release-v1",
        "config_sha256": _digest(config),
        "raw_release_required": True,
        "source_surface": "Findata REST",
        "source_requests": sorted(store.requests.values(), key=_canonical_bytes),
        "release_artifacts": [_artifact(path) for path in pre_manifest_paths],
        "eventxbench": config.get("eventxbench", {"data_access": "not_obtained", "use": "schema/method reference only"}),
        "limitations": [
            "shared-query candidates are not semantic gold labels",
            "historical active/open/indexed state is absent from current REST market detail",
            "REST data omit warehouse provenance columns",
            "exact-limit bare arrays are recursively narrowed and fail unresolved at one-second windows",
        ],
    }
    _write_json(release_dir / "data_manifest.json", data_manifest)

    write_audit_release(output_dir, summary=summary, funnel=funnel, l2_coverage=l2_coverage)
    _write_csv(output_dir / "trade_coverage.csv", trade_coverage, release_fields["trade_coverage.csv"])
    _write_csv(output_dir / "l2_asof.csv", asof_rows, release_fields["l2_asof.csv"])
    output_paths = sorted(path for path in output_dir.iterdir() if path.is_file() and path.name != "reconstruction_manifest.json")
    _write_json(output_dir / "reconstruction_manifest.json", {"schema_version": "replay-audit-manifest-v1", "artifacts": [_artifact(path) for path in output_paths]})
    return summary
