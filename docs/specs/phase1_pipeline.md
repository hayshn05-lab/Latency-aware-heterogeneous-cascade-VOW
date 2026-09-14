# Phase-one pipeline contract

Design version: phase1.v1. **Implementation status: draft; not frozen.** The user deferred experimental/baseline runs at goal closure. The contracts below describe the target interface, not proof every feature is implemented. Current code has tested cleaning, as-of context, baseline/cascade adapters, snapshot cash/depth primitives and isolated VOW. The runner is development-only; grouped splits, full label metrics, comprehensive failure accounting and actual-data integration remain unverified. See [handoff](../plans/phase1_execution.md).

Version: phase1.v1. Separate source storage, eligibility, observations, agent outputs and evaluator-only outcomes. Python 3.11 standard library throughout; raw records remain unchanged.

## Public seams

- `build_phase1(config)` reads cached SQLite records, writes versioned `p1_*` tables and a deterministic audit manifest; rerunning the same config/source is idempotent. A different source fingerprint or rule config creates a different release ID. No raw-table deletion.
- `observations(config, split)` yields event ID, source/receipt/decision times, post text, as-of candidates and prior market features. Context excludes future books, updated descriptions and labels. `strict` mode never falls back to conditional metadata. Deep corpus retrieval has an explicit cutoff and records evidence IDs and latency.
- `Agent.decide(observation)` or offline JSONL trajectories produce a validated action: event/condition/token direction, expectation, confidence, availability and compute cost. Shared adapters implement no-trade, consensus, momentum, fast/deep and cascade selection. Recorded predictions are a reproducible model-independent seam.
- `replay(config, actions)` advances chronologically through order arrivals and real source-specific snapshots, validates candidate membership/availability and applies depth/capital/expiry rules. It emits attempts, fills, positions, equity and metrics with manifests. Model agents never receive evaluator labels or future books.
- `evaluate_counterfactuals` uses the same execution primitive for G/W/VOW and reports missing pairs; never calls the router with these labels.

## Required cleaned tables

`p1_releases`: config/source fingerprints and state. `p1_tweets`: original clean posts and modeled receipt eligibility. `p1_markets`: normalized mapping, family and conditional metadata provenance. `p1_books`: normalized levels plus invalid/conflict barriers, partitioned by source. `p1_trades`: canonical YES trade proxies with side semantics marked unknown unless verified. `p1_market_eligibility`: strict/conditional availability intervals and supporting evidence. `p1_replay_intervals`: observed entry/exit structural support, evaluator-only. `p1_exclusions`: reason counts/row fingerprints. Strict and conditional views must be explicitly named.

Do not export future replay-interval support as an online universe filter. Cleaned tweets are eligible signals, not gold event-market links. Empty strict views must be reported honestly. Model actions select markets through retrieval; linking is not prefilled from future price moves.

## Verification obligations

Behavior tests cover receipt-vs-ingest independence, no future metadata, invalid-first-book rejection, bounded waits, explicit NO token handling, depth/fees, duplicate liquidity, delayed actions, missing exit/capital lock, label isolation, family splits, complete counters and deterministic rebuilds. Real-data verification compares source fingerprints and unchanged raw counts, runs offline twice, checks SQL integrity and reports usable conditional versus strict counts.

Freeze config/code hashes only after these checks; future windows reuse the same CLI and rules with a new release ID. Unknown semantics remain explicit gates, not guessed defaults.
