# Research plan: signal discovery, reasoning latency and trading value

Updated 2026-09-13. Historical-first, prospectively validated. The current task acquires one week of Findata data, builds an extensible database and measures replay readiness; it does not run a strategy.

## Question and estimand

Does deeper reasoning improve an event-driven trading decision enough to compensate for market discovery time, additional inference latency and trading costs?

For complete actions F and D, actual completion times tF and tD, and a common capital, fee and exit convention:

- G = U(D,tF) - U(F,tF)
- W = U(D,tD) - U(D,tF)
- VOW = G + W = U(D,tD) - U(F,tF)

W is signed and need not always be negative. The deep action at tF is a counterfactual attribution, not a tradable policy. Compare implementable policies at their actual availability and order-arrival times. Do not double-count compute or execution costs.

## Full pipeline

External post -> point-in-time market retrieval -> fast/deep reasoning and abstention -> structured action -> available signal -> marketable-order replay -> portfolio outcome.

An action contains market/token, direction or probability change, confidence, size limit, expiry and abstention reason. Relevance, direction, and positive net trading utility are different targets. Include unrelated posts, NONE, retrieval failures and concurrent-position constraints in the evaluation denominator.

Market indexing may happen in advance, but retain its coverage and update lag. Retrieval and reranking after the event consume time. Record source, receipt, retrieval completion, fast/deep completion, publication availability and order arrival. Missing receipt times require explicitly simulated latency scenarios, not claims of measured transport latency.

## Data scope

The initial warehouse release covers [2026-09-06, 2026-09-13) UTC for tweets, Polymarket trades and books. Market metadata uses scheduled overlap: end_date >= start and start_date < end or missing. This broad, retrospective collection rule is not proof of the historically tradable universe. Unknown dates and markets observed on tapes but missing from that roster must be reported separately.

SQLite preserves distinct source row versions, identifiers, source/ingest times and query provenance. Immutable SQL materializations support offline rebuilding. Retain every available outcome label; only verified YES/NO pairs enter the initial probability canonicalization and paired-book audit.

Local EventXBench T2 contains 543 train and 2,500 validation/test rows each. Train has 1,987 candidate markets and 310 gold markets, with 166 single-human and 377 silver labels. Validation/test lack post timestamps. The local export revision remains unverified. These files support later linking work, not automatic trading labels or a ready H2 sample. Their preset candidate lists omit market discovery cost. Known training timestamps end on 2026-06-28, so the September acquisition is not a direct join to that training set. A later linked experiment must either annotate this week or acquire an overlapping historical window; validation/test time coverage remains unverified.

## Evidence gates

- D0: schemas, coverage, completeness, market mapping and timestamp diagnostics.
- H0: as-of token trades; non-executable price-state proxies only.
- H1: transparent sensitivity to incomplete execution inputs; do not assume identified bounds.
- H2: verified historical market eligibility, semantic event link, outcome mapping, fresh valid required books, depth, fees, capital/exit rules and sufficient independent families. Snapshot replay still has behavioral assumptions; passive queues are not identified.
- P1: separately audited synchronized prospective recording and validation.

A clock-grid or sampled-post/book join is a structural coverage diagnostic, not a semantic event-market link. Good book coverage does not by itself establish H2. Historical lack of coverage on one REST path does not invalidate the warehouse.

## Sequence after this acquisition

The [weekly readiness report](../reports/weekly_replay_readiness.md) is the current empirical starting point. Acquisition is complete. The structural diagnostic does not yet establish a linked executable cohort.

1. Verify source/ingest clock semantics and complete metadata for observed trade/book identifiers. Establish historical indexed/open eligibility.
2. Select contiguous book intervals using data-quality criteria, then independently label contemporaneous event links and NONE cases. Alternatively acquire a verified EventXBench-overlapping window. Do not select by realized profit.
3. Build the as-of candidate index and measure retrieval recall and total signal-production latency. Validate a small linked entry/exit replay slice with explicit depth, freshness and cost assumptions.
4. Freeze family/embargo splits, signal encoding, order size, fee schedule, exits and capital constraints before modeling.
5. Compare no-trade, lexical/lightweight baselines, fast-only, always-deep, fixed cascade, cost-matched random escalation and VOW routing on a sealed test.
6. Report net utility, deployed capital, coverage/rejections, latency, family-clustered intervals and chronological portfolio risk; validate prospectively.

The 5,10,30,60,120,300,600-second grid and 1800-second marking diagnostic are designs, not demonstrated profit windows. The preserved tweet-count pilot cannot establish executable opportunity decay or general semantic alpha.
