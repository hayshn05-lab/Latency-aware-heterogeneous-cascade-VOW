"""Shared snapshot-scenario execution; no assumed passive fills."""
from bisect import bisect_left
import math


def next_snapshot(books, arrival, max_wait):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (arrival, max_wait)) or max_wait < 0:
        raise ValueError("Invalid arrival or wait")
    index = bisect_left(books, arrival, key=lambda b: b["ts"])
    if index == len(books) or books[index]["ts"] > arrival + max_wait:
        return None
    return books[index]



def replay_actions(actions, book_series, settings):
    """Chronological long-token simulation with atomic visible-depth fills.

    Actions must already be validated against model-safe observations. Future
    books are evaluator-only; they determine scheduling, never agent choices.
    """
    import heapq
    from collections import Counter
    initial = settings["initial_cash"]
    fee_rate = settings["fee_bps"] / 10000
    wait = settings["max_wait_seconds"]
    transport = settings["transport_seconds"]
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x < 0 for x in (initial, fee_rate, wait, transport)):
        raise ValueError("Invalid execution settings")
    cash = initial
    queue = []
    attempts = {}
    positions = {}
    open_conditions = set()
    fills = []
    equity = []
    remaining = {}
    fees = compute = turnover = deployed = realized = 0.0
    closed = 0
    for action in actions:
        event = str(action["event_id"])
        if event in attempts:
            raise ValueError("Duplicate event action")
        if not math.isfinite(action["available_ts"]) or action["available_ts"] < action["decision_ts"]:
            raise ValueError("Action precedes decision")
        cost = action.get("compute_cost", 0)
        if not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
            raise ValueError("Invalid compute cost")
        attempts[event] = {"event_id": event, "status": "pending", "route": action.get("route", "unspecified")}
        heapq.heappush(queue, (action["available_ts"], 1, event, "available", action, None))

    def execution(book, action, side):
        quantity = action["quantity"]
        if not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity <= 0:
            return None, "invalid_quantity"
        if not book.get("can_buy" if side == "buy" else "can_sell"):
            return None, "unusable_" + side + "_book"
        minimum = book.get("min_order_size")
        if minimum is not None and quantity < minimum:
            return None, "below_minimum_order"
        levels = book["asks" if side == "buy" else "bids"]
        key = (action["source"], action["asset_id"], book["ts"], side)
        left = remaining.get(key, [x[1] for x in levels])
        available = list(left)
        todo = quantity
        notional = 0.0
        limit = action.get("limit_price", 1) if side == "buy" else 0
        for index, (price, _) in enumerate(levels):
            if side == "buy" and price > limit:
                break
            take = min(todo, available[index])
            notional += take * price
            available[index] -= take
            todo -= take
            if todo <= 1e-9:
                break
        if todo > 1e-9:
            return None, "insufficient_depth_or_limit"
        return (notional, key, available), None

    while queue:
        ts, _, event, kind, action, book = heapq.heappop(queue)
        attempt = attempts[event]
        if kind == "available":
            cost = action.get("compute_cost", 0)
            cash -= cost
            compute += cost
            if action["direction"] == "NONE":
                attempt["status"] = action.get("abstention_reason", "abstain")
            else:
                arrival = ts + transport
                expiry = min(action["exit_due_ts"], action.get("expires_ts", action["exit_due_ts"]))
                if action["direction"] not in {"BUY_YES", "BUY_NO"}:
                    attempt["status"] = "invalid_direction"
                elif arrival >= expiry:
                    attempt["status"] = "expired_before_entry"
                else:
                    selected = next_snapshot(book_series.get((action["source"], action["asset_id"]), []), arrival, min(wait, expiry - arrival))
                    if selected is None or selected["ts"] >= expiry:
                        attempt["status"] = "missing_entry"
                    else:
                        attempt["entry_wait_seconds"] = selected["ts"] - arrival
                        heapq.heappush(queue, (selected["ts"], 2, event, "entry", action, selected))
        elif kind == "entry":
            executed, error = execution(book, action, "buy")
            if action["condition_id"] in open_conditions:
                attempt["status"] = "condition_already_open"
            elif error:
                attempt["status"] = error
            else:
                notional, key, left = executed
                fee = notional * fee_rate
                if notional + fee > cash:
                    attempt["status"] = "insufficient_capital"
                else:
                    remaining[key] = left
                    cash -= notional + fee
                    fees += fee
                    turnover += notional
                    deployed += notional + fee
                    positions[event] = {"event_id": event, "condition_id": action["condition_id"], "asset_id": action["asset_id"], "quantity": action["quantity"], "entry_ts": ts, "entry_notional": notional, "entry_fee": fee, "status": "open"}
                    open_conditions.add(action["condition_id"])
                    attempt["status"] = "open"
                    fills.append({"event_id": event, "side": "buy", "ts": ts, "quantity": action["quantity"], "notional": notional, "fee": fee, "asset_id": action["asset_id"]})
                    arrival = action["exit_due_ts"] + transport
                    selected = next_snapshot(book_series.get((action["source"], action["asset_id"]), []), arrival, wait)
                    if selected is None:
                        attempt["status"] = "censored_missing_exit"
                    else:
                        heapq.heappush(queue, (selected["ts"], 0, event, "exit", action, selected))
        else:
            executed, error = execution(book, action, "sell")
            if error:
                attempt["status"] = "censored_" + error
            else:
                notional, key, left = executed
                remaining[key] = left
                fee = notional * fee_rate
                cash += notional - fee
                fees += fee
                turnover += notional
                position = positions[event]
                pnl = notional - fee - position["entry_notional"] - position["entry_fee"]
                realized += pnl
                position.update(status="closed", exit_ts=ts, exit_notional=notional, exit_fee=fee, net_trading_pnl=pnl)
                open_conditions.remove(action["condition_id"])
                closed += 1
                attempt["status"] = "closed"
                fills.append({"event_id": event, "side": "sell", "ts": ts, "quantity": action["quantity"], "notional": notional, "fee": fee, "asset_id": action["asset_id"]})
        open_shares = sum(p["quantity"] for p in positions.values() if p["status"] == "open")
        equity.append({"ts": ts, "cash": cash, "lower": cash, "upper": cash + open_shares})
    peak_lower = peak_upper = initial
    dd_lower = dd_upper = 0.0
    for point in equity:
        peak_lower = max(peak_lower, point["lower"])
        peak_upper = max(peak_upper, point["upper"])
        dd_lower = max(dd_lower, peak_lower - point["upper"])
        dd_upper = max(dd_upper, peak_upper - point["lower"])
    opens = [p for p in positions.values() if p["status"] == "open"]
    return {"attempts": list(attempts.values()), "fills": fills, "positions": list(positions.values()), "equity_bounds": equity,
            "metrics": {"events": len(attempts), "entries": len(positions), "closed_positions": closed, "open_positions": len(opens),
                        "cash": cash, "fees_paid": fees, "compute_cost": compute, "turnover": turnover,
                        "capital_deployed_cumulative": deployed, "net_realized_pnl": realized - compute,
                        "return_on_deployed_capital_closed_only": (realized - compute) / sum(p["entry_notional"] + p["entry_fee"] for p in positions.values() if p["status"] == "closed") if closed else None,
                        "open_cost_basis": sum(p["entry_notional"] + p["entry_fee"] for p in opens),
                        "terminal_pnl_lower": cash - initial, "terminal_pnl_upper": cash + sum(p["quantity"] for p in opens) - initial,
                        "drawdown_lower_bound": max(0, dd_lower), "drawdown_upper_bound": max(0, dd_upper),
                        "fill_coverage": len(positions) / len(attempts) if attempts else None,
                        "status_counts": dict(Counter(a["status"] for a in attempts.values())),
                        "evidence": "conditional snapshot fills with explicit fee scenario; not observed executable PnL"}}
