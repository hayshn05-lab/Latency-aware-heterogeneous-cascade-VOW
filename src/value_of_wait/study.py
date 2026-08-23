"""Bundle construction and descriptive, non-executable price-move summaries."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any


def parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def iso_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_bundles(tweets: list[dict[str, Any]], gap_seconds: int, horizons: list[int]) -> list[dict[str, Any]]:
    ordered = sorted(tweets, key=lambda tweet: parse_time(tweet["timestamp"]))
    groups: list[list[dict[str, Any]]] = []
    for tweet in ordered:
        if not groups or (parse_time(tweet["timestamp"]) - parse_time(groups[-1][-1]["timestamp"])).total_seconds() > gap_seconds:
            groups.append([tweet])
        else:
            groups[-1].append(tweet)
    bundles: list[dict[str, Any]] = []
    for index, group in enumerate(groups, start=1):
        start, decision = parse_time(group[0]["timestamp"]), parse_time(group[-1]["timestamp"])
        bundle: dict[str, Any] = {"bundle_id": f"bundle-{index:04d}", "bundle_start": iso_time(start), "decision_time": iso_time(decision), "tweet_count": len(group), "tweet_ids": ",".join(str(tweet.get("tweet_id", "")) for tweet in group)}
        later = [parse_time(tweet["timestamp"]) for tweet in ordered if parse_time(tweet["timestamp"]) > decision]
        for horizon in horizons:
            bundle[f"clean_{horizon}"] = not any(time <= decision + timedelta(seconds=horizon) for time in later)
        bundles.append(bundle)
    return bundles


def _last_state(trades: list[dict[str, Any]], target: datetime, staleness_seconds: int) -> dict[str, Any] | None:
    prior = [trade for trade in trades if parse_time(trade["timestamp"]) <= target]
    if not prior:
        return None
    trade = max(prior, key=lambda item: parse_time(item["timestamp"]))
    age = (target - parse_time(trade["timestamp"])).total_seconds()
    if age > staleness_seconds:
        return None
    return {"price": float(trade["yes_price"]), "timestamp": trade["timestamp"], "age_seconds": age}


def study_observations(bundles: list[dict[str, Any]], market_trades: dict[str, list[dict[str, Any]]], horizons: list[int], staleness_seconds: int, terminal_move_floor: float) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    terminal = max(horizons)
    for bundle in bundles:
        decision = parse_time(bundle["decision_time"])
        baseline_target = parse_time(bundle["bundle_start"]) - timedelta(seconds=1)
        for market_id, raw_trades in sorted(market_trades.items()):
            trades = sorted(raw_trades, key=lambda trade: parse_time(trade["timestamp"]))
            baseline = _last_state(trades, baseline_target, staleness_seconds)
            endpoint = _last_state(trades, decision + timedelta(seconds=terminal), staleness_seconds)
            for horizon in horizons:
                target = decision + timedelta(seconds=horizon)
                delayed = _last_state(trades, target, staleness_seconds)
                eligible = baseline is not None and delayed is not None
                row: dict[str, Any] = {"bundle_id": bundle["bundle_id"], "market_id": market_id, "horizon_seconds": horizon, "clean": bool(bundle.get(f"clean_{horizon}", False)), "terminal_clean": bool(bundle.get(f"clean_{terminal}", False)), "eligible": eligible, "baseline_age_seconds": baseline["age_seconds"] if baseline else None, "delayed_age_seconds": delayed["age_seconds"] if delayed else None, "updated": None, "absolute_repricing_points": None, "remaining_move_proxy": None}
                if eligible:
                    row["updated"] = parse_time(delayed["timestamp"]) > decision
                    row["absolute_repricing_points"] = round(100 * abs(delayed["price"] - baseline["price"]), 12)
                    if row["terminal_clean"] and endpoint is not None and abs(endpoint["price"] - baseline["price"]) >= terminal_move_floor:
                        row["remaining_move_proxy"] = abs(endpoint["price"] - delayed["price"]) / abs(endpoint["price"] - baseline["price"])
                result.append(row)
    return result


def _iqr(values: list[float]) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    ordered = sorted(values)
    return (ordered[(len(ordered) - 1) // 4], ordered[(3 * (len(ordered) - 1)) // 4])


def summarize_delays(observations: list[dict[str, Any]], horizons: list[int]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for horizon in horizons:
        all_rows = [row for row in observations if row["horizon_seconds"] == horizon]
        eligible = [row for row in all_rows if row["eligible"]]
        clean = [row for row in eligible if row["clean"]]
        terminal_clean = [row for row in eligible if row.get("terminal_clean")]
        repricing = [float(row["absolute_repricing_points"]) for row in clean if row["absolute_repricing_points"] is not None]
        remaining = [float(row["remaining_move_proxy"]) for row in clean if row["remaining_move_proxy"] is not None]
        repricing_iqr = _iqr(repricing)
        remaining_iqr = _iqr(remaining)
        ages = [float(row["delayed_age_seconds"]) for row in clean if row["delayed_age_seconds"] is not None]
        age_iqr = _iqr(ages)
        rows.append({"horizon_seconds": horizon, "bundle_market_pairs": len(all_rows), "eligible_pairs": len(eligible), "clean_eligible_pairs": len(clean), "terminal_clean_eligible_pairs": len(terminal_clean), "coverage": len(eligible) / len(all_rows) if all_rows else None, "clean_coverage": len(clean) / len(all_rows) if all_rows else None, "updated_pairs": sum(bool(row["updated"]) for row in clean), "updated_fraction": sum(bool(row["updated"]) for row in clean) / len(clean) if clean else None, "repricing_n": len(repricing), "median_repricing_points": median(repricing) if repricing else None, "repricing_iqr_low_points": repricing_iqr[0], "repricing_iqr_high_points": repricing_iqr[1], "remaining_n": len(remaining), "median_remaining_move_proxy": median(remaining) if remaining else None, "remaining_iqr_low": remaining_iqr[0], "remaining_iqr_high": remaining_iqr[1], "median_delayed_age_seconds": median(ages) if ages else None, "delayed_age_iqr_low_seconds": age_iqr[0], "delayed_age_iqr_high_seconds": age_iqr[1], "missing_pairs": len(all_rows) - len(eligible)})
    return rows


def first_print_latencies(bundles: list[dict[str, Any]], market_trades: dict[str, list[dict[str, Any]]], *, terminal_horizon_seconds: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bundle in bundles:
        decision = parse_time(bundle["decision_time"])
        candidates = [parse_time(trade["timestamp"]) for trades in market_trades.values() for trade in trades if parse_time(trade["timestamp"]) > decision]
        if candidates:
            latency = (min(candidates) - decision).total_seconds()
            rows.append({"bundle_id": bundle["bundle_id"], "latency_seconds": latency, "within_terminal_horizon": latency <= terminal_horizon_seconds, "terminal_clean": bool(bundle.get(f"clean_{terminal_horizon_seconds}", False))})
    return rows
