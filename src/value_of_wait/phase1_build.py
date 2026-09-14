"""Offline, versioned materialization of phase-one research tables."""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

from .phase1_data import clean_book, clean_tweet, eligible_interval
from .replay_audit import normalize_market_tokens, ReplayValidationError
from .warehouse import canonical
from .weekly_audit import seconds
from .research_db import normalized_time

TABLES = ("tweets", "markets", "books", "trades", "market_eligibility", "replay_intervals", "exclusions")


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS p1_releases(release_id TEXT PRIMARY KEY, summary TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS p1_tweets(release_id TEXT, event_id TEXT, source_ts REAL, receipt_ts REAL, payload TEXT, row_sha256 TEXT, PRIMARY KEY(release_id,event_id));
    CREATE TABLE IF NOT EXISTS p1_markets(release_id TEXT, condition_id TEXT, family_id TEXT, payload TEXT, row_sha256 TEXT, PRIMARY KEY(release_id,condition_id));
    CREATE TABLE IF NOT EXISTS p1_books(release_id TEXT, source TEXT, asset_id TEXT, ts REAL, quality TEXT, payload TEXT, row_sha256 TEXT, PRIMARY KEY(release_id,source,asset_id,ts));
    CREATE TABLE IF NOT EXISTS p1_trades(release_id TEXT, row_sha256 TEXT, condition_id TEXT, asset_id TEXT, ts REAL, yes_price REAL, size REAL, payload TEXT, PRIMARY KEY(release_id,row_sha256));
    CREATE TABLE IF NOT EXISTS p1_market_eligibility(release_id TEXT, condition_id TEXT, source TEXT, mode TEXT, available_from REAL, available_until REAL, evidence TEXT, PRIMARY KEY(release_id,condition_id,source,mode));
    CREATE TABLE IF NOT EXISTS p1_replay_intervals(release_id TEXT, source TEXT, asset_id TEXT, entry_ts REAL, exit_ts REAL, horizon INTEGER, PRIMARY KEY(release_id,source,asset_id,entry_ts,horizon));
    CREATE TABLE IF NOT EXISTS p1_exclusions(release_id TEXT, kind TEXT, reason TEXT, rows INTEGER, PRIMARY KEY(release_id,kind,reason));
    CREATE VIEW IF NOT EXISTS p1_strict_markets AS SELECT m.*,e.source,e.available_from,e.available_until FROM p1_markets m JOIN p1_market_eligibility e USING(release_id,condition_id) WHERE e.mode='strict';
    CREATE VIEW IF NOT EXISTS p1_conditional_markets AS SELECT m.*,e.source,e.available_from,e.available_until FROM p1_markets m JOIN p1_market_eligibility e USING(release_id,condition_id) WHERE e.mode='conditional';
    CREATE INDEX IF NOT EXISTS p1_tweet_time ON p1_tweets(release_id,receipt_ts,event_id);
    CREATE INDEX IF NOT EXISTS p1_trade_time ON p1_trades(release_id,condition_id,ts);
    """)


def source_fingerprint(conn, config):
    counts = {}
    hashes = {}
    for kind in ("markets", "tweets", "books", "trades"):
        h = hashlib.sha256()
        n = 0
        for value, in conn.execute("SELECT row_sha256 FROM records WHERE kind=? ORDER BY row_sha256", (kind,)):
            h.update((value + "\n").encode())
            n += 1
        counts[kind], hashes[kind] = n, h.hexdigest()
    parent = config.get("source_manifest")
    return {"counts": counts, "ordered_row_sha256": hashes,
            "source_manifest": parent,
            "source_manifest_sha256": hashlib.sha256(Path(parent).read_bytes()).hexdigest() if parent else None}


def table_fingerprints(conn, rid):
    result = {}
    for table in TABLES:
        columns = conn.execute("PRAGMA table_info(p1_" + table + ")").fetchall()
        keys = [row[1] for row in sorted(columns, key=lambda row: row[5]) if row[5]]
        h = hashlib.sha256()
        for row in conn.execute("SELECT * FROM p1_" + table + " WHERE release_id=? ORDER BY " + ",".join(keys), (rid,)):
            h.update((canonical(row) + "\n").encode())
        result[table] = h.hexdigest()
    return result


def build_phase1(config):
    release = Path(config["release"])
    release.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config["database"])
    try:
        schema(conn)
        source = source_fingerprint(conn, config)
        rules = {k: v for k, v in config.items() if k not in {"database", "release", "source_manifest"}}
        code = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__), Path(__file__).with_name("phase1_data.py"))}
        release_id = digest({"rules": rules, "source": source, "code": code})[:24]
        existing = conn.execute("SELECT summary FROM p1_releases WHERE release_id=?", (release_id,)).fetchone()
        if existing:
            summary = json.loads(existing[0])
            for table in TABLES:
                actual = conn.execute("SELECT count(*) FROM p1_" + table + " WHERE release_id=?", (release_id,)).fetchone()[0]
                if actual != summary["counts"][table]:
                    raise ValueError("Stored phase-one release is incomplete")
            if table_fingerprints(conn, release_id) != summary["table_sha256"]:
                raise ValueError("Stored phase-one table fingerprint mismatch")
        else:
            with conn:
                summary = materialize(conn, config, release_id, source, rules, code)
                summary["table_sha256"] = table_fingerprints(conn, release_id)
                conn.execute("INSERT INTO p1_releases VALUES(?,?)", (release_id, canonical(summary)))
        (release / "data_manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary
    finally:
        conn.close()


def materialize(conn, config, rid, source, rules, code):
    start = seconds(config["window"]["start"])
    end = seconds(config["window"]["end_exclusive"])
    if start is None or end is None or start >= end:
        raise ValueError("Invalid source window")
    excluded = Counter()
    selected_sources = set(config["sources"])
    book_assets = {r[0] for r in conn.execute("SELECT DISTINCT asset_id FROM books WHERE source_time>=? AND source_time<?", (normalized_time(config["window"]["start"]), normalized_time(config["window"]["end_exclusive"])))}
    markets = {}
    owners = defaultdict(set)
    conflicts = set()
    for sha, raw in conn.execute("SELECT row_sha256,payload FROM markets ORDER BY row_sha256"):
        row = json.loads(raw)
        try:
            mapping = normalize_market_tokens(row)
        except ReplayValidationError:
            excluded[("markets", "non_yes_no_or_invalid_mapping")] += 1
            continue
        cid = mapping["condition_id"]
        pair = (mapping["yes_asset_id"], mapping["no_asset_id"])
        for asset in pair:
            owners[asset].add(cid)
        if not set(pair) & book_assets:
            excluded[("markets", "no_observed_book_asset")] += 1
            continue
        question = str(row.get("question") or "").strip()
        if not question:
            excluded[("markets", "missing_question")] += 1
            continue
        events = row.get("events") or []
        if isinstance(events, str):
            try:
                events = json.loads(events)
            except ValueError:
                events = []
        families = sorted({str(e["id"]) for e in events if isinstance(e, dict) and e.get("id")}) if isinstance(events, list) else []
        value = {"condition_id": cid, "yes_asset_id": pair[0], "no_asset_id": pair[1], "question": question,
                 "family_ids": families, "family_id": "event:" + ",".join(families) if families else "unknown:" + cid,
                 "created_ts": seconds(row.get("market_created_at")), "start_ts": seconds(row.get("start_date")),
                 "end_ts": seconds(row.get("end_date")), "closed_ts": seconds(row.get("closed_time")),
                 "metadata_basis": "conditional_frozen_retrospective_question_and_mapping"}
        if cid in markets and markets[cid][0] != value:
            conflicts.add(cid)
        markets[cid] = value, sha
    markets = {cid: entry for cid, entry in markets.items() if cid not in conflicts and all(len(owners[a]) == 1 for a in (entry[0]["yes_asset_id"], entry[0]["no_asset_id"]))}
    excluded[("markets", "conflicting_condition_versions")] = len(conflicts)
    asset_map = {}
    for cid, (row, sha) in markets.items():
        conn.execute("INSERT INTO p1_markets VALUES(?,?,?,?,?)", (rid, cid, row["family_id"], canonical(row), sha))
        asset_map[row["yes_asset_id"]] = cid, "YES"
        asset_map[row["no_asset_id"]] = cid, "NO"
    print("phase1 markets normalized", len(markets), flush=True)
    tweet_conflicts = {str(r[0]) for r in conn.execute("SELECT entity_id FROM tweets GROUP BY entity_id HAVING count(*)>1")}
    for sha, raw in conn.execute("SELECT row_sha256,payload FROM tweets ORDER BY row_sha256"):
        row = json.loads(raw)
        clean, reason = clean_tweet(row, feed_delay_seconds=config["feed_delay_seconds"])
        if str(row.get("tweet_id")) in tweet_conflicts:
            reason = "conflicting_tweet_versions"
        if not reason and not start <= clean["source_ts"] < end:
            reason = "outside_window"
        if reason:
            excluded[("tweets", reason)] += 1
            continue
        conn.execute("INSERT INTO p1_tweets VALUES(?,?,?,?,?,?)", (rid, clean["event_id"], clean["source_ts"], clean["receipt_ts"], canonical(clean), sha))
    print("phase1 tweets normalized", flush=True)
    series = defaultdict(list)
    qualities = defaultdict(Counter)
    for sha, raw in conn.execute("SELECT row_sha256,payload FROM books ORDER BY row_sha256"):
        row = json.loads(raw)
        if row.get("source") not in selected_sources:
            excluded[("books", "source_not_selected")] += 1
            continue
        if str(row.get("asset_id")) not in asset_map:
            excluded[("books", "unmapped_asset")] += 1
            continue
        book = clean_book(row)
        if book["ts"] is None or not start <= book["ts"] < end:
            excluded[("books", "outside_window_or_invalid_time")] += 1
            continue
        expected = asset_map[book["asset_id"]][0]
        if row.get("condition_id") and row["condition_id"].lower() != expected:
            book.update(quality="mapping_conflict", can_buy=False, can_sell=False)
        series[(book["source"], book["asset_id"])].append((book, sha))
    first_seen = {}
    for (src, asset), entries in sorted(series.items()):
        groups = defaultdict(list)
        for book, sha in entries:
            groups[book["ts"]].append((book, sha))
        normalized = []
        for ts, versions in sorted(groups.items()):
            book, sha = versions[0]
            if len({canonical(b) for b, _ in versions}) > 1:
                book = dict(book, quality="conflict", can_buy=False, can_sell=False)
            if len(versions) > 1:
                excluded[("books", "duplicate_or_conflicting_same_time_rows")] += len(versions) - 1
            book["source_row_hashes"] = sorted(s for _, s in versions)
            conn.execute("INSERT INTO p1_books VALUES(?,?,?,?,?,?,?)", (rid, src, asset, ts, book["quality"], canonical(book), sha))
            qualities[src][book["quality"]] += 1
            normalized.append(book)
        first_seen[(src, asset)] = normalized[0]["ts"]
        times = [b["ts"] for b in normalized]
        for entry in normalized:
            if not entry["can_buy"] or sum(x[1] for x in entry["asks"]) < config["quantity"]:
                continue
            if entry["min_order_size"] is not None and config["quantity"] < entry["min_order_size"]:
                continue
            for horizon in config["exit_horizons_seconds"]:
                index = bisect_left(times, entry["ts"] + horizon)
                if index == len(times):
                    continue
                exit_book = normalized[index]
                if exit_book["ts"] > entry["ts"] + horizon + config["max_wait_seconds"] or not exit_book["can_sell"] or sum(x[1] for x in exit_book["bids"]) < config["quantity"]:
                    continue
                if not eligible_interval(markets[asset_map[asset][0]][0], entry, exit_book, config["quantity"]):
                    continue
                conn.execute("INSERT INTO p1_replay_intervals VALUES(?,?,?,?,?,?)", (rid, src, asset, entry["ts"], exit_book["ts"], horizon))
    print("phase1 books and structural intervals normalized", flush=True)
    for cid, (market, _) in markets.items():
        for src in sorted(selected_sources):
            seen = [first_seen[(src, a)] for a in (market["yes_asset_id"], market["no_asset_id"]) if (src, a) in first_seen]
            if not seen or market["created_ts"] is None or market["start_ts"] is None or market["end_ts"] is None:
                excluded[("eligibility", "missing_quote_or_lifecycle")] += 1
                continue
            lower = max(start, market["created_ts"], market["start_ts"], min(seen))
            upper = min(end, market["end_ts"], market["closed_ts"] if market["closed_ts"] is not None else end)
            if lower >= upper:
                excluded[("eligibility", "no_lifecycle_overlap")] += 1
                continue
            conn.execute("INSERT INTO p1_market_eligibility VALUES(?,?,?,?,?,?,?)", (rid, cid, src, "conditional", lower, upper, "frozen retrospective metadata; prior quote presence; NOT historical indexed/open proof"))
    import math
    for sha, raw in conn.execute("SELECT row_sha256,payload FROM trades ORDER BY row_sha256"):
        row = json.loads(raw)
        asset = str(row.get("asset_id") or "")
        if asset not in asset_map:
            excluded[("trades", "outside_mapped_book_cohort")] += 1
            continue
        cid, outcome = asset_map[asset]
        ts = seconds(row.get("ts"))
        price, size = row.get("price"), row.get("size")
        if ts is None or not start <= ts < end or not isinstance(price, (int, float)) or not math.isfinite(price) or not 0 <= price <= 1 or not isinstance(size, (int, float)) or not math.isfinite(size) or size <= 0 or (row.get("condition_id") and row["condition_id"].lower() != cid):
            excluded[("trades", "invalid_time_price_size_or_mapping")] += 1
            continue
        payload = {"source": row.get("source"), "raw_side": row.get("side"), "side_semantics": "unverified", "outcome": outcome}
        conn.execute("INSERT INTO p1_trades VALUES(?,?,?,?,?,?,?,?)", (rid, sha, cid, asset, ts, price if outcome == "YES" else 1 - price, size, canonical(payload)))
    for (kind, reason), n in sorted(excluded.items()):
        conn.execute("INSERT INTO p1_exclusions VALUES(?,?,?,?)", (rid, kind, reason, n))
    counts = {name: conn.execute("SELECT count(*) FROM p1_" + name + " WHERE release_id=?", (rid,)).fetchone()[0] for name in TABLES}
    counts["strict_eligibility"] = 0
    return {"version": config["version"], "release_id": rid, "source": source, "rules": rules, "code_sha256": code,
            "counts": counts, "book_quality_by_source": {k: dict(v) for k, v in qualities.items()},
            "exclusions": {kind: {reason: n for (k, reason), n in excluded.items() if k == kind} for kind in sorted({k for k, r in excluded})},
            "evidence": "conditional snapshot simulation; no verified historical H2 candidate universe",
            "semantic_gold_labels": 0, "settlement_labels": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--offline", action="store_true", help="Explicit offline mode; this command never uses network")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = build_phase1(config)
    print(json.dumps({"release_id": result["release_id"], "counts": result["counts"]}, sort_keys=True))
