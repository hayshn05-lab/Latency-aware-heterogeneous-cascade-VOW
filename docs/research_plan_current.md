# Research plan: selective information acquisition and snapshot trading

Updated 2026-09-14. Phase one uses the acquired September week. The primary question is **when additional information acquisition and semantic reasoning improve net trading utility enough to justify their cost and delay**. The intended contribution is an implementable selective cascade plus a Value of Waiting analysis, not an assumed profitable latency window.

## Accepted direction and corrections

Use discrete snapshot-based, execution-aware simulation at minute-scale decision cadences. Keep REST polling and WebSocket sources separate. Do not require every event to pass all nine old freshness checkpoints. Entry and exit are individual scheduled actions, evaluated on subsequent observed snapshots within a bounded wait.

Warehouse ingest time is provenance, not a measurement of real-time tweet receipt. The primary historical simulation uses source time plus explicitly configured direct-feed delay; this is a feed scenario, not observed live latency or a mathematical upper bound. Actual receipt logs can replace that assumption later. Do not interpret source-versus-ingest utility differences as a measured causal pipeline cost.

Deep means additional historical information retrieval and reasoning. Do not insert artificial waiting to make deep appear expensive. Measure actual path latency, report same-execution-snapshot frequency, and distinguish measured model runtime from simulated historical feed/execution delay. A zero measured wait effect is a valid result.

The initial audit found a median of 655.7785 seconds across 729 asset-level median gaps (mixed sources). Source-separated re-audit confirms REST pooled/asset median gaps of 299.997549 seconds, 274 assets, and 256 assets with exactly 2,016 weekly rows. WS has 524 assets with a median asset-level median gap of 2859.80925 seconds. Thus REST supports a five-minute design; the mixed statistic must not be used to deny that. Five/fifteen/thirty-minute decision cadences are design sensitivities; execution uses actual source-specific timestamps.

## Evidence and eligibility

Raw data remain immutable. New versioned tables separate normalized records, candidate availability evidence, replayable snapshot intervals and exclusions. No future book or return selects the online candidate roster. Future exit coverage is an evaluator result; rejected and censored attempts remain in denominators.

Strict historical candidates require independently verified indexed/open metadata at the decision time. Current warehouse metadata is not sufficient. A separately named **conditional snapshot simulation** may freeze retrospectively observed question/token metadata and explicitly assume it was unchanged and indexed. That cohort cannot be called a historically verified candidate universe or executable H2. Never silently promote conditional rows into strict tables.

Books observed before a decision establish prior quote presence, not immutable historical wording or continuous open status. Keep current descriptions, outcomes and post-decision updates out of strict model contexts. Future/today web search is forbidden for historical agent evidence. Deep retrieval must use an archived as-of corpus with publication and simulated/observed availability metadata.

## Estimand and strategy

For actions F and D and their complete availability times tF,tD:

- G = U(D,tF) - U(F,tF)
- W = U(D,tD) - U(D,tF)
- VOW = G + W

U uses the same snapshot execution, fees, fixed exit convention and order size. Counterfactual D at tF is evaluator-only; it is never a policy input. Compute cost is accounted separately once. For missing counterfactual paths, VOW is unavailable, not zero. Portfolio opportunity conflicts make isolated action decomposition different from total portfolio utility; report both separately.

The cascade retrieves candidate markets, runs fast inference, then chooses abstain, accept fast, or acquire more information and run deep. The trade action is separately BUY_YES, BUY_NO or NONE. Route labels are not order directions. Learned VOW uses train-only paired outcomes and pre-routing features; calibration/thresholds freeze on validation.

## Phase-one scope and evaluation

See [experiment draft](specs/phase1_experiment.md), [common interface](specs/phase1_pipeline.md), and [baseline evidence](baseline_evidence.md). English original posts form the primary text cohort; other languages and replies/quotes are explicit exclusions pending context support. All qualifying posts remain, including unrelated posts and no-candidate outcomes. Gold semantic labels and settlement labels are absent unless independently supplied, so those metrics are unavailable, not inferred from price moves.

Primary exits are 30 and 60 minutes; settlement is disabled until authenticated outcomes and dates exist. Use realistic observed depth with explicit fee/slippage scenarios, no passive fills, no instantaneous liquidity reuse, and a chronological capital ledger. Seven days are a pilot for plumbing and feasibility, not a definitive Sharpe/APY or generalization claim.

## Handoff and deferred execution

The user narrowed this goal to completing the design and wrapping up, with no experiment or baseline runs. The design documents are complete; the already-started cleaning materialization is preserved. Common replay modules are implementation drafts with synthetic tests, not a fully verified/frozen experiment framework.

See [handoff](plans/phase1_execution.md) for completed work, final cleaned counts and explicit deferred implementation. Finish interface validation, grouped splits, label-based metrics and independent real-data verification in a subsequent task before model studies. No model, actual-data strategy baseline, production signal or deployment was run here.
