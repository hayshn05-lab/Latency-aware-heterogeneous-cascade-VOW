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


def _outcome_tokens(row: dict[str, Any]) -> dict[str, str]:
    outcomes = _value(row, "outcomes", "tokens") or []
    if not isinstance(outcomes, list):
        return {}
    if all(isinstance(outcome, dict) for outcome in outcomes):
        mapping: dict[str, str] = {}
        for outcome in outcomes:
            name = str(_value(outcome, "name", "outcome", "label") or "").strip().upper()
            token = _value(outcome, "token_id", "tokenId", "id", "asset_id")
            if name not in {"YES", "NO"} or token is None:
                return {}
            token_id = str(token).strip()
            if name in mapping or not token_id:
                return {}
            mapping[name] = token_id
        return mapping if set(mapping) == {"YES", "NO"} and mapping["YES"] != mapping["NO"] else {}
    token_ids = row.get("clob_token_ids")
    if not isinstance(token_ids, list) or len(outcomes) != len(token_ids):
        return {}
    mapping = {}
    for label, token in zip(outcomes, token_ids):
        name, token_id = str(label).strip().upper(), str(token).strip() if token is not None else ""
        if name not in {"YES", "NO"} or name in mapping or not token_id:
            return {}
        mapping[name] = token_id
    return mapping if set(mapping) == {"YES", "NO"} and mapping["YES"] != mapping["NO"] else {}


def parse_markets(payload: Any) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for row in _rows(payload):
        mapping = _outcome_tokens(row)
        if mapping:
            copy = dict(row)
            condition_id = str(_value(row, "condition_id") or "").strip()
            source_market_id = str(_value(row, "market_id", "id") or "").strip()
            copy["market_id"] = condition_id or source_market_id
            if condition_id and source_market_id:
                copy["source_market_id"] = source_market_id
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
        timestamp = _value(row, "timestamp", "created_at", "createdAt", "time", "ts")
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
