"""Model-safe observations and shared strategy adapters for phase-one replay."""
from bisect import bisect_right
import hashlib
import math
import re
from .warehouse import canonical

STOP_WORDS = set("a an the is are was were will would should could be been to of in on at by for with and or as this that it its from into about has have had not no yes new news".split())


def terms(text):
    return set(re.findall(r"[a-z0-9]+", text.lower())) - STOP_WORDS


def past_book(books, ts, max_age):
    index = bisect_right(books, ts, key=lambda row: row["ts"]) - 1
    if index < 0 or ts - books[index]["ts"] > max_age:
        return None
    return books[index]


def features_for(market, series, ts, settings):
    features = {}
    for outcome in ("yes", "no"):
        books = series.get((settings["source"], market[outcome + "_asset_id"]), [])
        book = past_book(books, ts, settings["feature_max_age_seconds"])
        ask = book["asks"][0][0] if book and book.get("can_buy") else None
        bid = book["bids"][0][0] if book and book.get("can_sell") else None
        features[outcome + "_ask"] = ask
        features[outcome + "_bid"] = bid
        features[outcome + "_mid"] = (ask + bid) / 2 if ask is not None and bid is not None else None
        features[outcome + "_ask_depth"] = sum(x[1] for x in book["asks"]) if ask is not None else None
        features[outcome + "_age_seconds"] = ts - book["ts"] if book else None
    prior = past_book(series.get((settings["source"], market["yes_asset_id"]), []), ts - settings["lookback_seconds"], settings["feature_max_age_seconds"])
    previous_mid = (prior["asks"][0][0] + prior["bids"][0][0]) / 2 if prior and prior.get("can_buy") and prior.get("can_sell") else None
    features["momentum"] = features["yes_mid"] - previous_mid if features["yes_mid"] is not None and previous_mid is not None else None
    return features


def make_observation(post, markets, book_series, settings):
    cadence = settings["cadence_seconds"]
    if cadence <= 0:
        raise ValueError("Cadence must be positive")
    decision = math.ceil(post["receipt_ts"] / cadence) * cadence
    query = terms(post["text"])
    ranked = []
    universe_n = 0
    for market in markets:
        if not market["available_from"] <= decision < market["available_until"]:
            continue
        universe_n += 1
        words = terms(market["question"])
        score = len(query & words) / math.sqrt(max(1, len(words)))
        if score <= 0:
            continue
        candidate = {k: market[k] for k in ("condition_id", "question", "yes_asset_id", "no_asset_id", "family_id", "metadata_basis", "available_until")}
        candidate["retrieval_score"] = score
        candidate["features"] = features_for(market, book_series, decision, settings)
        ranked.append(candidate)
    ranked.sort(key=lambda row: (-row["retrieval_score"], row["condition_id"]))
    result = {"schema": "phase1.observation.v1", "event_id": post["event_id"], "source_ts": post["source_ts"], "receipt_ts": post["receipt_ts"],
              "decision_ts": decision, "input_cutoff_ts": decision,
              "retrieval_complete_ts": decision + settings["retrieval_seconds"],
              "retrieval_timing_basis": "configured_simulation_seconds",
              "exit_due_ts": decision + settings["exit_horizon_seconds"], "text": post["text"], "author": post["author"],
              "candidate_universe_size": universe_n, "candidates": ranked[:settings["top_k"]], "source": settings["source"]}
    result["context_sha256"] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result


STRATEGIES = {"no_trade", "market_consensus", "momentum", "fast_only", "always_deep", "confidence_cascade", "random_cascade", "vow_cascade"}


def decide(strategy, observation, settings, predictor=None, context_provider=None):
    """Return the same action schema for every strategy; predictors see no tape."""
    if strategy not in STRATEGIES:
        raise ValueError("Unknown strategy")
    action = {"event_id": observation["event_id"], "decision_ts": observation["decision_ts"],
              "available_ts": observation["retrieval_complete_ts"], "exit_due_ts": observation["exit_due_ts"],
              "source": observation["source"], "direction": "NONE", "quantity": settings["quantity"],
              "compute_cost": 0.0, "route": "none", "strategy": strategy, "context_sha256": observation["context_sha256"]}
    candidates = observation["candidates"]
    if strategy == "no_trade" or not candidates:
        action["abstention_reason"] = "no_trade_policy" if strategy == "no_trade" else "no_candidates"
        return action
    if strategy == "market_consensus":
        action["forecasts"] = [{"condition_id": c["condition_id"], "settlement_probability_proxy": c["features"]["yes_mid"]} for c in candidates]
        action["abstention_reason"] = "market_deference"
        return action
    if strategy == "momentum":
        valid = [c for c in candidates if c["features"]["momentum"] is not None and abs(c["features"]["momentum"]) >= settings["momentum_threshold"]]
        if not valid:
            action["abstention_reason"] = "no_momentum_signal"
            return action
        candidate = max(valid, key=lambda c: (abs(c["features"]["momentum"]), c["condition_id"]))
        expected = min(1, max(0, candidate["features"]["yes_mid"] + candidate["features"]["momentum"]))
        prediction = {"condition_id": candidate["condition_id"], "expected_yes_price": expected, "confidence": 1}
        action["available_ts"] += settings.get("inference_seconds", 0)
        action["route"] = "market_only"
    else:
        if predictor is None:
            raise ValueError("A recorded or measured predictor is required")
        path = "deep" if strategy == "always_deep" else "fast"
        model_context = context_provider(path, observation) if context_provider else observation
        prediction = predictor(path, model_context)
        validate_prediction(prediction, model_context)
        action["prediction_context_sha256"] = model_context["context_sha256"]
        action["available_ts"] += prediction["latency_seconds"]
        action["compute_cost"] += prediction["compute_cost"]
        action["route"] = path
        if strategy.endswith("cascade"):
            escalate = False
            if strategy == "confidence_cascade":
                escalate = prediction["confidence"] < settings["confidence_threshold"]
            elif strategy == "random_cascade":
                key = str(settings.get("seed", 0)) + ":" + observation["event_id"]
                value = int(hashlib.sha256(key.encode()).hexdigest()[:16], 16) / 2**64
                escalate = value < settings["random_escalation_rate"]
            else:
                # Frozen coefficients fitted outside the model runner on train only.
                weights = settings["vow_weights"]
                feature = {"bias": 1, "uncertainty": 1 - prediction["confidence"], "candidate_count": len(candidates),
                           "retrieval_margin": candidates[0]["retrieval_score"] - (candidates[1]["retrieval_score"] if len(candidates) > 1 else 0)}
                if set(weights) - set(feature):
                    raise ValueError("Unknown or unsafe VOW feature")
                value = sum(weights[k] * feature[k] for k in weights)
                action["predicted_incremental_utility"] = value
                escalate = value > settings["expected_deep_compute_cost"]
            if escalate:
                model_context = context_provider("deep", observation) if context_provider else observation
                prediction = predictor("deep", model_context)
                validate_prediction(prediction, model_context)
                action["prediction_context_sha256"] = model_context["context_sha256"]
                action["available_ts"] += prediction["latency_seconds"]
                action["compute_cost"] += prediction["compute_cost"]
                action["route"] = "fast_then_deep"
    target = prediction.get("condition_id")
    if target is None or prediction.get("direction") == "NONE":
        action["abstention_reason"] = "model_abstain"
        return action
    candidate = next(c for c in candidates if c["condition_id"] == target)
    q = prediction["expected_yes_price"]
    fee_rate = settings["fee_bps"] / 10000
    options = []
    for label, expected in (("yes", q), ("no", 1 - q)):
        ask = candidate["features"][label + "_ask"]
        if ask is not None:
            edge = expected - ask * (1 + fee_rate)
            options.append((edge, label, expected))
    if not options:
        action["abstention_reason"] = "no_observed_ask"
        return action
    edge, label, expected = max(options)
    if edge < settings["min_edge"]:
        action["abstention_reason"] = "insufficient_predicted_edge"
        return action
    action.update(condition_id=target, asset_id=candidate[label + "_asset_id"], direction="BUY_" + label.upper(),
                  limit_price=max(0, (expected - settings["min_edge"]) / (1 + fee_rate)),
                  expires_ts=min(observation["exit_due_ts"], candidate["available_until"]), family_id=candidate["family_id"],
                  confidence=prediction["confidence"], expected_yes_price=q)
    return action


def validate_prediction(prediction, observation):
    if prediction.get("event_id") != observation["event_id"] or prediction.get("context_sha256") != observation["context_sha256"]:
        raise ValueError("Prediction context mismatch")
    if prediction.get("input_cutoff_ts") != observation["input_cutoff_ts"]:
        raise ValueError("Prediction evidence cutoff mismatch")
    for key in ("latency_seconds", "compute_cost", "confidence"):
        value = prediction.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError("Invalid prediction timing, cost or confidence")
    if prediction["confidence"] > 1:
        raise ValueError("Invalid prediction confidence")
    target = prediction.get("condition_id")
    if target is not None:
        if target not in {c["condition_id"] for c in observation["candidates"]}:
            raise ValueError("Prediction selected an unavailable candidate")
        q = prediction.get("expected_yes_price")
        if not isinstance(q, (int, float)) or not math.isfinite(q) or not 0 <= q <= 1:
            raise ValueError("Invalid expected horizon price")



def deep_context(observation, corpus, *, lookback_seconds, top_k):
    """Additional archived source text, available by the common input cutoff."""
    query = terms(observation["text"] + " " + " ".join(c["question"] for c in observation["candidates"]))
    cutoff = observation["input_cutoff_ts"]
    ranked = []
    for post in corpus:
        if post["event_id"] == observation["event_id"] or not cutoff - lookback_seconds <= post["receipt_ts"] <= cutoff:
            continue
        overlap = len(query & terms(post["text"]))
        if overlap:
            ranked.append((overlap, post))
    ranked.sort(key=lambda item: (-item[0], -item[1]["receipt_ts"], item[1]["event_id"]))
    result = {k: v for k, v in observation.items() if k != "context_sha256"}
    result["historical_evidence"] = [{k: post[k] for k in ("event_id", "source_ts", "receipt_ts", "text", "author")} for _, post in ranked[:top_k]]
    result["evidence_basis"] = "archived_original_posts_with_simulated_feed_availability"
    result["context_sha256"] = hashlib.sha256(canonical(result).encode()).hexdigest()
    return result
