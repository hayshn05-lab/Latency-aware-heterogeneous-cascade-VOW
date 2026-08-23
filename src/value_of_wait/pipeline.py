"""Acquisition, content-addressed cache replay, and bounded Findata pilot modes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .client import FindataClient, token_from_environment
from .outputs import write_outputs
from .parsing import parse_markets, parse_trades, parse_tweets
from .study import build_bundles, first_print_latencies, parse_time, study_observations, summarize_delays

DEFAULT_ENDPOINTS = {
    "tweets": "/kols/{handle}/tweets/history", "market_search": "/prediction-markets/markets/search",
    "market_detail": "/prediction-markets/markets/polymarket/{condition_id}",
    "trades": "/prediction-markets/trades/polymarket/{condition_id}",
    "orderbook": "/prediction-markets/orderbook/polymarket/{asset_id}",
}


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def cache_request_key(endpoint: str, params: dict[str, Any]) -> str:
    return _digest({"endpoint": endpoint, "params": dict(sorted(params.items()))})


def save_cache_entry(cache: Path, endpoint: str, params: dict[str, Any], payload: Any, *, retrieved_at: str | None = None) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    request_digest, content_digest = cache_request_key(endpoint, params), _digest(payload)
    safe = re.sub(r"[^A-Za-z0-9]+", "-", endpoint).strip("-") or "response"
    path = cache / f"{safe}-{request_digest}-{content_digest}.json"
    record = {"request": {"endpoint": endpoint, "params": dict(sorted(params.items()))}, "retrieved_at": retrieved_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "response_sha256": content_digest, "payload": payload}
    path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    return path


def load_cache_entry(cache: Path, endpoint: str, params: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    key = cache_request_key(endpoint, params)
    paths = sorted(cache.glob(f"*-{key}-*.json"))
    if not paths:
        raise FileNotFoundError(f"no cached response for {endpoint}")
    if len(paths) != 1:
        raise RuntimeError(f"multiple content versions cached for {endpoint}")
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    expected = {"endpoint": endpoint, "params": dict(sorted(params.items()))}
    if record.get("request") != expected or record.get("response_sha256") != _digest(record.get("payload")):
        raise RuntimeError(f"invalid cached response for {endpoint}")
    return record["payload"], {"retrieved_at": record.get("retrieved_at")}


def _page_rows(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    container = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(container, dict):
        rows = container.get("items") or container.get("results") or container.get("data")
        if rows is None and any(key in container for key in ("id", "market_id", "condition_id")):
            rows = [container]
        cursor = container.get("next_cursor") or container.get("nextCursor")
    elif isinstance(container, list):
        rows, cursor = container, None
    else:
        rows, cursor = [], None
    return [row for row in (rows or []) if isinstance(row, dict)], str(cursor) if cursor else None


def fetch_paginated(client: FindataClient, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        request = dict(params)
        if cursor:
            request["cursor"] = cursor
        page, cursor = _page_rows(client.get_json(endpoint, request))
        rows.extend(page)
        if not cursor:
            return rows


def _manifest(endpoint: str, params: dict[str, Any], payload: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    rows, _ = _page_rows(payload)
    return {"endpoint": endpoint, "params": dict(sorted(params.items())), "retrieved_at": metadata.get("retrieved_at"), "row_count": len(rows), "sha256": _digest(payload)}


def _get_source(endpoint: str, params: dict[str, Any], cache: Path, offline: bool, client: FindataClient | None) -> tuple[Any, dict[str, Any]]:
    if offline:
        return load_cache_entry(cache, endpoint, params)
    assert client is not None
    payload = {"data": fetch_paginated(client, endpoint, params)}
    path = save_cache_entry(cache, endpoint, params, payload)
    return payload, {"retrieved_at": json.loads(path.read_text(encoding="utf-8"))["retrieved_at"]}


def title_matches(question: str, prefix: str, window_label: str) -> bool:
    normal = " ".join(question.split()).casefold()
    return normal.startswith(" ".join(prefix.split()).casefold()) and normal.endswith(" ".join(window_label.split()).casefold() + "?")


def _in_window(tweets: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    return [tweet for tweet in tweets if parse_time(start) <= parse_time(tweet["timestamp"]) <= parse_time(end)]


def timestamp_precision(tweets: list[dict[str, Any]], market_trades: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    def stream(values: list[str]) -> tuple[int, bool]:
        digits, nonzero = [], False
        for value in values:
            match = re.search(r"\.(\d+)(?:Z|[+-]\d\d:\d\d)?$", value)
            if match:
                fraction = match.group(1); digits.append(len(fraction)); nonzero |= int(fraction) != 0
            else: digits.append(0)
        return (min(digits) if digits else 0), nonzero
    tweet_digits, tweet_nonzero = stream([str(row["timestamp"]) for row in tweets])
    trade_digits, trade_nonzero = stream([str(row["timestamp"]) for rows in market_trades.values() for row in rows])
    milliseconds = bool(tweet_digits >= 3 and trade_digits >= 3 and tweet_nonzero and trade_nonzero)
    least = min(tweet_digits, trade_digits)
    return {"classification": "milliseconds" if milliseconds else ("coarse sub-second" if least > 0 else "seconds"), "milliseconds_identifiable": milliseconds, "least_fractional_digits": least}


def _endpoints(config: dict[str, Any]) -> dict[str, str]: return DEFAULT_ENDPOINTS | config.get("endpoints", {})


def _collect(config: dict[str, Any], *, offline: bool, environment: dict[str, str] | None, client: FindataClient | None):
    cache, endpoints = Path(config.get("cache_dir", "data/raw/findata")), _endpoints(config)
    if not offline and client is None: client = FindataClient(config["base_url"], token_from_environment(environment))
    tweet_params = {"start": config["window_start"], "end": config["window_end"]}
    tweet_endpoint, search_params = endpoints["tweets"].format(handle=config["handle"]), {"query": config["search_query"]}
    tweet_payload, tweet_meta = _get_source(tweet_endpoint, tweet_params, cache, offline, client)
    search_payload, search_meta = _get_source(endpoints["market_search"], search_params, cache, offline, client)
    manifest = [_manifest(tweet_endpoint, tweet_params, tweet_payload, tweet_meta), _manifest(endpoints["market_search"], search_params, search_payload, search_meta)]
    validation, included = [], []
    for candidate in _page_rows(search_payload)[0]:
        condition_id = str(candidate.get("condition_id", candidate.get("market_id", candidate.get("id", ""))))
        detail_endpoint = endpoints["market_detail"].format(condition_id=condition_id)
        detail_payload, detail_meta = _get_source(detail_endpoint, {}, cache, offline, client)
        manifest.append(_manifest(detail_endpoint, {}, detail_payload, detail_meta))
        detail_rows = _page_rows(detail_payload)[0]; row = detail_rows[0] if detail_rows else candidate
        market_id, question = str(row.get("condition_id", row.get("market_id", row.get("id", condition_id)))), str(row.get("question", ""))
        parsed = parse_markets({"data": [row]})
        if not title_matches(question, config["title_prefix"], config["title_window_label"]):
            validation.append({"market_id": market_id, "decision": "excluded", "reason": "question does not exactly match configured title family and window"})
        elif not parsed:
            validation.append({"market_id": market_id, "decision": "excluded", "reason": "ambiguous or missing YES/NO outcome-to-token mapping"})
        else:
            validation.append({"market_id": market_id, "decision": "included", "reason": "exact configured title/window match with unambiguous YES/NO mapping"}); included.append(parsed[0])
    trades: dict[str, list[dict[str, Any]]] = {}
    for market in included:
        endpoint = endpoints["trades"].format(condition_id=market["market_id"]); params = {"start": config["window_start"], "end": config["window_end"]}
        payload, metadata = _get_source(endpoint, params, cache, offline, client)
        manifest.append(_manifest(endpoint, params, payload, metadata)); trades[market["market_id"]] = parse_trades(payload, market["outcome_tokens"])
    return manifest, validation, _in_window(parse_tweets(tweet_payload), config["window_start"], config["window_end"]), trades, included, cache, client


def run_pilot(config: dict[str, Any], output: Path, *, offline: bool, environment: dict[str, str] | None = None, client: FindataClient | None = None) -> None:
    manifest, validation, tweets, trades, _, _, _ = _collect(config, offline=offline, environment=environment, client=client)
    horizons = list(config["horizons_seconds"]); bundles = build_bundles(tweets, int(config["bundle_gap_seconds"]), horizons)
    observations = study_observations(bundles, trades, horizons, int(config["staleness_seconds"]), float(config["terminal_move_floor"]))
    write_outputs(output, manifest=manifest, market_validation=validation, bundles=bundles, observations=observations, delay_profile=summarize_delays(observations, horizons), first_print=first_print_latencies(bundles, trades), timestamp_precision=timestamp_precision(tweets, trades))


def audit_pilot(config: dict[str, Any], output: Path, *, offline: bool, environment: dict[str, str] | None = None, client: FindataClient | None = None) -> None:
    manifest, validation, _, _, included, cache, client = _collect(config, offline=offline, environment=environment, client=client)
    rows = []
    for market in included:
        for outcome, asset_id in sorted(market["outcome_tokens"].items()):
            endpoint = _endpoints(config)["orderbook"].format(asset_id=asset_id); params = {"start": config["window_start"], "end": config["window_end"]}
            payload, metadata = _get_source(endpoint, params, cache, offline, client); manifest.append(_manifest(endpoint, params, payload, metadata))
            snapshots, _ = _page_rows(payload); stamps = [str(row.get("timestamp", row.get("created_at", ""))) for row in snapshots if row.get("timestamp", row.get("created_at"))]
            rows.append({"market_id": market["market_id"], "outcome": outcome, "asset_id": asset_id, "snapshot_count": len(snapshots), "first_timestamp": min(stamps) if stamps else None, "last_timestamp": max(stamps) if stamps else None, "coverage": bool(stamps), "execution_verdict": "not execution-estimable: aligned order-book coverage and fill model are not established"})
    from .outputs import write_audit_outputs
    write_audit_outputs(output, manifest, validation, rows)
