"""Config-driven offline experiment harness with a recorded-prediction seam."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from .phase1_interface import STRATEGIES, make_observation, decide, deep_context
from .phase1_replay import replay_actions
from .warehouse import canonical
from .weekly_audit import quantile


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(canonical(row) + "\n")


def run_experiment(config, strategy, *, predictions_path=None, predictor=None):
    if strategy not in STRATEGIES:
        raise ValueError("Unknown strategy")
    if config["mode"] not in {"strict", "conditional"}:
        raise ValueError("Explicit strict or conditional mode required")
    if config.get("split", "development") != "development":
        raise ValueError("A frozen family split manifest is required for non-development runs")
    semantic = strategy not in {"no_trade", "market_consensus", "momentum"}
    if semantic and predictions_path is None and predictor is None:
        raise ValueError("Semantic strategies require recorded predictions")
    data_path = Path(config["data_manifest"])
    data_manifest = json.loads(data_path.read_text(encoding="utf-8"))
    rid = data_manifest["release_id"]
    records = {}
    if predictions_path:
        for line in Path(predictions_path).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            key = (row["event_id"], row["path"])
            if key in records:
                raise ValueError("Duplicate prediction trajectory")
            records[key] = row
    used_predictions = []

    def predict(path, observation):
        result = predictor(path, observation) if predictor else records[(observation["event_id"], path)]
        used_predictions.append(dict(result, path=path))
        return result

    conn = sqlite3.connect(f"file:{Path(config['database']).as_posix()}?mode=ro", uri=True)
    try:
        if conn.execute("SELECT 1 FROM p1_releases WHERE release_id=?", (rid,)).fetchone() is None:
            raise ValueError("Unknown cleaned release")
        markets = []
        for payload, lower, upper in conn.execute("SELECT m.payload,e.available_from,e.available_until FROM p1_markets m JOIN p1_market_eligibility e USING(release_id,condition_id) WHERE m.release_id=? AND e.source=? AND e.mode=? ORDER BY m.condition_id", (rid, config["source"], config["mode"])):
            markets.append(dict(json.loads(payload), available_from=lower, available_until=upper))
        books = defaultdict(list)
        for asset, payload in conn.execute("SELECT asset_id,payload FROM p1_books WHERE release_id=? AND source=? ORDER BY asset_id,ts", (rid, config["source"])):
            books[(config["source"], asset)].append(json.loads(payload))
        posts = [json.loads(row[0]) for row in conn.execute("SELECT payload FROM p1_tweets WHERE release_id=? ORDER BY receipt_ts,event_id", (rid,))]
    finally:
        conn.close()
    print("phase1 experiment inputs", len(posts), "posts", len(markets), "markets", sum(map(len, books.values())), "books", flush=True)
    code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(Path(__file__).parent.glob("phase1_*.py"))}
    frozen = {k: v for k, v in config.items() if k not in {"database", "output", "data_manifest"}}
    provenance = {"data_release_id": rid, "data_manifest_sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
                  "settings": frozen, "strategy": strategy, "code_sha256": code,
                  "predictions_sha256": hashlib.sha256(Path(predictions_path).read_bytes()).hexdigest() if predictions_path else None,
                  "prediction_basis": "external_callable_not_pinned" if predictor else "recorded_jsonl" if predictions_path else "deterministic_market_control"}
    run_id = hashlib.sha256(canonical(provenance).encode()).hexdigest()[:24]
    output = Path(config["output"]) / strategy / run_id
    output.mkdir(parents=True, exist_ok=True)
    actions = []
    observations = []
    deep_inputs = []

    def context(path, observation):
        if path == "fast":
            return observation
        return deep_context(observation, posts, lookback_seconds=config.get("evidence_lookback_seconds", 86400), top_k=config.get("evidence_top_k", 10))

    for post in posts:
        observation = make_observation(post, markets, books, config)
        observations.append(observation)
        if config.get("export_deep_contexts") and observation["candidates"]:
            deep_inputs.append(context("deep", observation))
        action = decide(strategy, observation, config, predict if semantic else None, context)
        actions.append(action)
    result = replay_actions(actions, books, config)
    metrics = result["metrics"]
    total_latency = [a["available_ts"] - o["receipt_ts"] for a, o in zip(actions, observations)]
    compute_latency = [a["available_ts"] - o["retrieval_complete_ts"] for a, o in zip(actions, observations)]
    candidate_n = sum(bool(o["candidates"]) for o in observations)
    routes = Counter(a["route"] for a in actions)
    family_pnl = defaultdict(list)
    by_event = {a["event_id"]: a for a in actions}
    for position in result["positions"]:
        if position["status"] == "closed":
            family_pnl[by_event[position["event_id"]].get("family_id", "unknown")].append(position["net_trading_pnl"])
    cluster_means = [sum(v) / len(v) for k, v in family_pnl.items() if not k.startswith("unknown")]
    metrics.update(candidate_events=candidate_n, candidate_coverage=candidate_n / len(posts) if posts else None,
                   route_counts=dict(routes), escalation_fraction=routes["fast_then_deep"] / len(posts) if posts else None,
                   total_latency_seconds={"p50": quantile(total_latency, .5), "p95": quantile(total_latency, .95)},
                   inference_and_tool_seconds={"p50": quantile(compute_latency, .5), "p95": quantile(compute_latency, .95)},
                   settlement_brier=None, semantic_accuracy=None, retrieval_recall=None,
                   label_status="No independent semantic or settlement labels supplied",
                   family_summary={"N": len(cluster_means), "iqr_low": quantile(cluster_means, .25), "iqr_high": quantile(cluster_means, .75), "basis": "descriptive metadata-family mean closed PnL; independence unverified"},
                   run_scope=config.get("split", "development"), candidate_mode=config["mode"])
    write_jsonl(output / "observations.jsonl", observations)
    if deep_inputs:
        write_jsonl(output / "deep_contexts.jsonl", deep_inputs)
    write_jsonl(output / "actions.jsonl", actions)
    write_jsonl(output / "predictions_used.jsonl", used_predictions)
    for key in ("attempts", "fills", "positions", "equity_bounds"):
        write_jsonl(output / (key + ".jsonl"), result[key])
    write_json(output / "metrics.json", metrics)
    artifacts = {p.name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in sorted(output.iterdir()) if p.is_file() and p.name != "data_manifest.json"}
    write_json(output / "data_manifest.json", dict(provenance, run_id=run_id, artifacts=artifacts,
               rows={"observations": len(observations), "actions": len(actions), "fills": len(result["fills"])},
               evidence="conditional snapshot simulation" if config["mode"] == "conditional" else "strict candidate eligibility; execution remains a declared scenario"))
    return {"output": str(output), "run_id": run_id, "metrics": metrics}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="no_trade")
    parser.add_argument("--predictions")
    parser.add_argument("--offline", action="store_true", help="This runner never accesses a network")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = run_experiment(config, args.strategy, predictions_path=args.predictions)
    print(json.dumps({"run_id": result["run_id"], "output": result["output"], "events": result["metrics"]["events"], "entries": result["metrics"]["entries"]}, sort_keys=True))
