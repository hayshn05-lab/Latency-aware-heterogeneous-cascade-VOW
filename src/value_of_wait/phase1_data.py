"""Versioned phase-one data contracts; ingestion is never simulated receipt."""
import math
from .weekly_audit import seconds


def clean_tweet(row, *, feed_delay_seconds):
    if not isinstance(feed_delay_seconds, (int, float)) or not math.isfinite(feed_delay_seconds) or feed_delay_seconds < 0:
        raise ValueError("feed delay must be finite and nonnegative")
    stamp = seconds(row.get("created_at"))
    if stamp is None:
        return None, "invalid_timestamp"
    if row.get("lang") != "en":
        return None, "unsupported_language"
    if row.get("tweet_type") != "original" or row.get("is_reply"):
        return None, "unsupported_context"
    text = str(row.get("text") or "").strip()
    author = str(row.get("author_username") or row.get("kol_username") or "").strip()
    identity = str(row.get("tweet_id") or "").strip()
    if not text or not author or not identity:
        return None, "missing_identity_or_text"
    return {"event_id": identity, "source_ts": stamp, "receipt_ts": stamp + feed_delay_seconds,
            "receipt_basis": "source_plus_simulated_feed_delay", "text": text, "author": author}, None


def clean_book(row):
    """Preserve invalid observations as barriers and one-sided usable depth."""
    from .replay_audit import parse_l2_snapshot, ReplayValidationError
    result = {"asset_id": str(row.get("asset_id") or ""), "ts": seconds(row.get("snapshot_ts")),
              "source": str(row.get("source") or ""), "quality": "malformed",
              "bids": [], "asks": [], "can_buy": False, "can_sell": False,
              "min_order_size": None, "tick_size": None}
    try:
        parsed = parse_l2_snapshot(row)
        for key in ("bids", "asks"):
            result[key] = [[float(x["price"]), float(x["size"])] for x in parsed[key]]
        for key in ("min_order_size", "tick_size"):
            if parsed[key] is not None:
                value = float(parsed[key])
                if not math.isfinite(value) or value <= 0:
                    raise ValueError("invalid order constraint")
                result[key] = value
    except (ReplayValidationError, ValueError, TypeError):
        return result
    bids, asks = result["bids"], result["asks"]
    if bids and asks and bids[0][0] >= asks[0][0]:
        result["quality"] = "crossed"
    else:
        result["quality"] = "two_sided" if bids and asks else "bid_only" if bids else "ask_only" if asks else "empty"
        result["can_buy"], result["can_sell"] = bool(asks), bool(bids)
    return result


def eligible_interval(market, entry, exit_book, quantity):
    required = [market.get(k) for k in ("created_ts", "start_ts", "end_ts")]
    if any(v is None for v in required):
        return False
    end = min(market["end_ts"], market.get("closed_ts") if market.get("closed_ts") is not None else market["end_ts"])
    if not max(market["created_ts"], market["start_ts"]) <= entry["ts"] < exit_book["ts"] < end:
        return False
    if not entry.get("can_buy") or not exit_book.get("can_sell"):
        return False
    for book, side in ((entry, "asks"), (exit_book, "bids")):
        if book.get("min_order_size") is not None and quantity < book["min_order_size"]:
            return False
        if sum(level[1] for level in book[side]) < quantity:
            return False
    return True
