"""Tolerant parsers and outcome-safe trade canonicalization."""
from __future__ import annotations

from typing import Any


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("items", "results", "markets", "tweets", "trades", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
        if isinstance(value, dict):
            nested = _rows(value)
            if nested:
                return nested
    return []


def _value(row: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in row:
            return row[name]
    return None


def parse_markets(payload: Any) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _rows(payload):
        outcomes = _value(row, "outcomes", "tokens") or []
        mapping: dict[str, str] = {}
        for outcome in outcomes:
            if not isinstance(outcome, dict):
                continue
            name = str(_value(outcome, "name", "outcome", "label") or "").strip().upper()
            token = _value(outcome, "token_id", "tokenId", "id", "asset_id")
            if name in {"YES", "NO"} and token is not None:
                if name in mapping:
                    mapping = {}
                    break
                mapping[name] = str(token)
        if set(mapping) == {"YES", "NO"} and mapping["YES"] != mapping["NO"]:
            copy = dict(row)
            copy["market_id"] = str(_value(row, "market_id", "id", "condition_id") or "")
            copy["outcome_tokens"] = mapping
            parsed.append(copy)
    return parsed


def parse_tweets(payload: Any) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _rows(payload):
        timestamp = _value(row, "timestamp", "created_at", "createdAt", "time")
        if timestamp is not None:
            copy = dict(row)
            copy["tweet_id"] = str(_value(row, "tweet_id", "id", "id_str") or "")
            copy["timestamp"] = str(timestamp)
            parsed.append(copy)
    return parsed


def parse_trades(payload: Any, outcome_tokens: dict[str, str]) -> list[dict[str, Any]]:
    token_to_outcome = {str(token): outcome for outcome, token in outcome_tokens.items()}
    parsed: list[dict[str, Any]] = []
    for row in _rows(payload):
        token = _value(row, "token_id", "tokenId", "asset_id", "assetId")
        price = _value(row, "price", "value")
        timestamp = _value(row, "timestamp", "created_at", "createdAt", "time")
        if str(token) not in token_to_outcome or price is None or timestamp is None:
            continue
        try:
            raw_price = float(price)
        except (TypeError, ValueError):
            continue
        if not 0 <= raw_price <= 1:
            continue
        copy = dict(row)
        copy["token_id"] = str(token)
        copy["timestamp"] = str(timestamp)
        copy["yes_price"] = raw_price if token_to_outcome[str(token)] == "YES" else 1 - raw_price
        parsed.append(copy)
    return parsed
