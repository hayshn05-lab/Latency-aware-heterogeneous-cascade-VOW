"""Online acquisition and credential-free cache replay for the narrow pilot."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .client import FindataClient, token_from_environment
from .outputs import write_outputs
from .parsing import parse_markets, parse_trades, parse_tweets
from .study import build_bundles, first_print_latencies, parse_time, study_observations, summarize_delays


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _cache_file(cache: Path, name: str) -> Path:
    return cache / f"{name}.json"


def _load_cache(cache: Path, name: str) -> tuple[Any, dict[str, Any]]:
    payload = json.loads(_cache_file(cache, name).read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "payload" in payload:
        return payload["payload"], {"retrieved_at": payload.get("retrieved_at")}
    return payload, {"retrieved_at": None}


def _save_cache(cache: Path, name: str, payload: Any) -> dict[str, Any]:
    cache.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _cache_file(cache, name).write_text(json.dumps({"payload": payload, "retrieved_at": retrieved_at}, sort_keys=True), encoding="utf-8")
    return {"retrieved_at": retrieved_at}


def _page_rows(payload: Any) -> tuple[list[dict[str, Any]], str | None]:
    container = payload.get("data", payload) if isinstance(payload, dict) else payload
    if isinstance(container, dict):
        rows = container.get("items") or container.get("results") or container.get("data") or []
        cursor = container.get("next_cursor") or container.get("nextCursor")
    elif isinstance(container, list):
        rows, cursor = container, None
    else:
        rows, cursor = [], None
    return [row for row in rows if isinstance(row, dict)], str(cursor) if cursor else None


def fetch_paginated(client: FindataClient, endpoint: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Read every cursor page; cursors never form part of a cache key or report secret."""
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        request = dict(params)
        if cursor:
            request["cursor"] = cursor
        payload = client.get_json(endpoint, request)
        page, cursor = _page_rows(payload)
        rows.extend(page)
        if not cursor:
            return rows


def _manifest(endpoint: str, params: dict[str, Any], payload: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    rows, _ = _page_rows(payload)
    return {"endpoint": endpoint, "params": dict(sorted(params.items())), "retrieved_at": metadata.get("retrieved_at"), "row_count": len(rows), "sha256": _digest(payload)}


def _get_source(name: str, endpoint: str, params: dict[str, Any], cache: Path, offline: bool, client: FindataClient | None) -> tuple[Any, dict[str, Any]]:
    if offline:
        return _load_cache(cache, name)
    assert client is not None
    rows = fetch_paginated(client, endpoint, params)
    payload = {"data": rows}
    return payload, _save_cache(cache, name, payload)


def _in_window(tweets: list[dict[str, Any]], start: str, end: str) -> list[dict[str, Any]]:
    minimum, maximum = parse_time(start), parse_time(end)
    return [tweet for tweet in tweets if minimum <= parse_time(tweet["timestamp"]) <= maximum]


def _timestamp_precision(tweets: list[dict[str, Any]], market_trades: dict[str, list[dict[str, Any]]]) -> str:
    timestamps = [str(row["timestamp"]) for row in tweets] + [str(row["timestamp"]) for trades in market_trades.values() for row in trades]
    return "milliseconds" if timestamps and all("." in value.split("Z", 1)[0] for value in timestamps) else "seconds"


def run_pilot(config: dict[str, Any], output: Path, *, offline: bool, environment: dict[str, str] | None = None) -> None:
    cache = Path(config.get("cache_dir", "data/raw/findata"))
    client = None if offline else FindataClient(config["base_url"], token_from_environment(environment))
    tweet_params = {"handle": config["handle"], "start": config["window_start"], "end": config["window_end"]}
    market_params = {"query": config["search_query"]}
    tweet_payload, tweet_meta = _get_source("tweets", "tweets", tweet_params, cache, offline, client)
    market_payload, market_meta = _get_source("markets", "markets", market_params, cache, offline, client)
    manifest = [_manifest("tweets", tweet_params, tweet_payload, tweet_meta), _manifest("markets", market_params, market_payload, market_meta)]
    tweets = _in_window(parse_tweets(tweet_payload), config["window_start"], config["window_end"])
    query_words = [word.lower() for word in config["search_query"].split()]
    parsed = {market["market_id"]: market for market in parse_markets(market_payload)}
    validation: list[dict[str, Any]] = []
    included: list[dict[str, Any]] = []
    for row in _page_rows(market_payload)[0]:
        market_id = str(row.get("market_id", row.get("id", row.get("condition_id", ""))))
        question = str(row.get("question", ""))
        market = parsed.get(market_id)
        if market is None:
            validation.append({"market_id": market_id, "decision": "excluded", "reason": "ambiguous or missing YES/NO outcome-to-token mapping"})
        elif not all(word in question.lower() for word in query_words):
            validation.append({"market_id": market_id, "decision": "excluded", "reason": "question does not match configured search query"})
        else:
            validation.append({"market_id": market_id, "decision": "included", "reason": "unambiguous YES/NO mapping and query match"})
            included.append(market)
    market_trades: dict[str, list[dict[str, Any]]] = {}
    for market in included:
        market_id = market["market_id"]
        params = {"market_id": market_id}
        payload, metadata = _get_source(f"trades_{market_id}", "trades", params, cache, offline, client)
        manifest.append(_manifest("trades", params, payload, metadata))
        market_trades[market_id] = parse_trades(payload, market["outcome_tokens"])
    horizons = list(config["horizons_seconds"])
    bundles = build_bundles(tweets, int(config["bundle_gap_seconds"]), horizons)
    observations = study_observations(bundles, market_trades, horizons, int(config["staleness_seconds"]), float(config["terminal_move_floor"]))
    write_outputs(output, manifest=manifest, market_validation=validation, bundles=bundles, observations=observations, delay_profile=summarize_delays(observations, horizons), first_print=first_print_latencies(bundles, market_trades), timestamp_precision=_timestamp_precision(tweets, market_trades))
