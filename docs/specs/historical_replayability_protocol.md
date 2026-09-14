# Historical Replayability Protocol

**Version:** 1.0
**Date:** 2026-08-30
**Scope:** data construction and execution-replay validation only

## 1. Research target

The project is historical-first, with prospective recording used to validate
transport, receipt-time, and live-execution assumptions.  The primary question
is:

> Does deeper semantic reasoning create enough incremental trading value to
> pay for its decision latency, fees, spread, and depth consumption?

Historical L2 replay is the intended main quantitative evidence only after the
audit in this protocol passes.  A reported warehouse row count is not evidence
that the relevant event--market windows are replayable.

## 2. Counterfactual quantities versus strategies

Let `F` be the fast action available at time `t_F`, `D` the deep action available
at `t_D`, and `U(a, B_t)` the marked utility of action `a` executed against the
eligible book `B_t`, including configured fees and depth consumption.

\[
GG_i = U(D_i, B_{t_F}) - U(F_i, B_{t_F})
\]

\[
WW_i = U(D_i, B_{t_D}) - U(D_i, B_{t_F})
\]

\[
VOW_i = GG_i + WW_i
      = U(D_i, B_{t_D}) - U(F_i, B_{t_F})
\]

`GG` and `WW` are a counterfactual attribution.  `D_i` was not yet known at
`t_F`, so `U(D_i, B_{t_F})` is not an implementable trade.  Implementable
strategies are evaluated separately: fast-only, deep-after-wait, fixed-delay
baselines, and a frozen router.  They may be compared with VOW attribution, but
their PnL must never be described as the counterfactual components themselves.

## 3. Evidence tiers

| Tier | Required data | Defensible claim |
|---|---|---|
| H2 | Point-in-time event/market link; verified YES/NO asset map; fresh, full historical L2 at entry/deep/exit; outcomes; fees | Execution-aware historical backtest of marketable orders, subject to remaining behavioral assumptions |
| H1 | Same as H2, but incomplete depth or one required book is unavailable | Bounded execution sensitivity only; no headline executable PnL |
| H0 | Token-level trades and timestamps, but replayable L2 fails | Non-executable price-state/repricing analysis only |
| P1 | Prospectively recorded exchange messages with synchronized receipt timestamps | Validation of feed latency, sub-second ordering, and live book reconstruction; not automatically historical generalization |

Passive queue fills require order lifecycle and queue-position evidence beyond
H2 and are out of scope for the starter replay.

## 4. Formal event--market--L2 funnel

Every dataset release must report both row counts and independent family counts
at each stage:

1. candidate external events;
2. semantically linked markets that are proven active, open, and indexed at the
   event timestamp;
3. pairs whose required historical-L2 window exists;
4. pairs with valid, non-crossed, sufficiently fresh entry/deep/exit books;
5. pairs with verified outcomes and an evaluable holding period;
6. independent event families after grouping brackets/siblings and applying the
   temporal embargo.

Calendar overlap alone is a diagnostic proxy, not proof of historical open and
index state.  Unverified candidates remain in the exclusions table and cannot
enter the strict funnel denominator after stage 1.

## 5. Replayability pass criteria

The H2 gate passes only when all of the following are measured on the joined
sample rather than inferred from provider-wide counts:

- `condition_id` is a 32-byte hexadecimal Polymarket identifier;
- distinct numeric YES and NO `asset_id` values are recovered from point-in-time
  or immutable market metadata;
- trade and book records join to those identifiers without unexplained aliases;
- book timestamps have documented semantics and are selected strictly as-of the
  decision timestamp;
- snapshot rows are complete states, or an initial state plus an uninterrupted,
  sequence-checked delta stream can be reconstructed;
- bids and asks parse into positive depth, valid prices, and a non-crossed book;
- snapshot cadence, age at every decision, gaps, duplicates, and coverage
  concentration are reported;
- a pre-registered maximum book age is enforced; missing or stale books are
  excluded, never converted to zero movement or a fill;
- depth walking can fill the configured order size at each required timestamp;
- outcome and marking timestamps are verified; and
- raw extracts, queries, exclusions, configuration, and derived outputs have
  deterministic hashes.

The primary audit grid is 5, 10, 30, 60, 120, 300, and 600 seconds.  Thirty
minutes is an outcome-marking diagnostic.  Sub-second hypotheses are not tested
unless both event receipt and book data have real sub-second precision.

## 6. Data contracts

### 6.1 Market/token mapping

Required normalized fields are `condition_id`, `yes_asset_id`, `no_asset_id`,
`market_start_ts`, `market_end_ts`, `indexed_ts`, `family_id`, and provenance.
The provider's numeric `market_id` is retained only as `source_market_id`; it is
not interchangeable with `condition_id`.

### 6.2 Trades

Required fields are `trade_id`, `condition_id`, `asset_id`, `ts`, `price`,
`size`, and `side`.  Prices are canonicalized to YES probability only after an
unambiguous asset mapping.  A REST response at its hard row limit is marked
potentially truncated unless pagination/completeness is independently proven.

### 6.3 L2 snapshots

Required fields are `asset_id`, `condition_id`, `snapshot_ts`, `bids`, `asks`,
`tick_size`, `min_order_size`, `hash`, and source provenance.  Each level must
contain price and size.  The audit records level counts, top of book, spread,
available depth, duplicate hashes, inter-snapshot gaps, and as-of staleness.
Whether arrays are full depth, capped depth, or deltas must be proven from the
source contract; shape alone is insufficient.

## 7. Versioned dataset layout

```text
data/
  raw/findata/replay_audit_v1/       # immutable, ignored API/SQL responses
  raw/eventxbench/replay_audit_v1/   # immutable, ignored release inputs
  interim/replay_audit_v1/           # local normalized rows
  releases/replay_audit_v1/          # committed manifest, indices, funnel, exclusions
outputs/replay_audit_v1/              # deterministic aggregate audit results
```

Raw records can remain access-controlled and ignored, but the committed release
must state how to obtain them and contain their SHA-256 digests.  A fresh clone
without the matching raw release is not described as source-reproducible.

## 8. Stage boundary

This stage may implement parsing, identifier validation, strict as-of selection,
stale-book rejection, deterministic reconstruction, a marketable-order depth
walk, split-integrity validation, and audit reporting.  It must not tune prompts,
run routers, optimize strategies, or make executable-PnL claims before H2 passes.
