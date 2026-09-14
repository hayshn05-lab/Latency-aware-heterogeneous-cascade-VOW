# Phase-one experiment draft

Status: experiment design draft completed 2026-09-14; execution deferred by the user. These settings are proposals for validation, not a final frozen study or an instruction to launch runs. Initial sample is the September 6-12 weekly release. Numerical choices below are initial preregistered engineering defaults, not tuned performance findings.

## Cohort, clocks and split

Primary posts: English originals, nonempty text and author, valid integer-second UTC source time; one immutable version per tweet ID, conflicting versions excluded. No topical/return filter. Replies and quotes need unavailable parent context and are separate exclusions. Preserve NONE and no-candidate posts.

Markets: verified binary mapping, nonempty question, explicit family identity, source-specific historical quote support. Clean all valid mapped books but retain invalid observations as execution barriers. Current mutable metadata cannot prove strict eligibility. Maintain strict and conditional tables; conditional uses a declared frozen-question/token mapping assumption, scheduled lifecycle bounds and past quote evidence. It is a simulation cohort, not historical H2.

Receipt = source + feed_delay (primary 5s; sensitivities 0/30/60s), independent of warehouse ingest. Source ingestion stays in provenance. Models receive only as-of evidence; simulated availability does not establish actual historical delivery.

Cadences 300/900/1800s use UTC grid ceilings of receipt; main 300s. Fast/deep timings come from recorded completed paths, including retrieval and inference; fixture values only test plumbing. No forced deep latency. Execution transport delay primary 1s. Exit due time is initial decision epoch + 1800 or 3600s, common to F and D; unavailable/expired late actions abstain.

Proposed calendar split: train September 6-8, validation September 9-10, test September 11-12. Embargo = maximum lookback/holding/TTL boundary buffer, initially 7200s. A market family crossing temporal partitions is excluded from multi-split confirmatory evaluation (not reassigned with leaked history); connected families and event bundles stay together. The week may yield too few families: report that and use development-only feasibility, not a weak sealed-test claim. Model inputs contain no split labels or realized future returns. All tuning uses train/validation only.

## Baselines and proposed cascade

| ID | Definition |
|---|---|
| no_trade | Every event yields NONE; still counts in coverage denominator. |
| market_consensus | As-of market YES probability forecast; no independent trading edge. Brier only with real settlement labels. |
| momentum | Past-only 15-minute YES midpoint change, requiring fresh observations at both ends; trade direction only above 0.02 absolute change, no signal when under-resolved. |
| fast_only | Shared candidate retrieval + fast model; no deeper corpus search. |
| always_deep | Shared retrieval + archived as-of evidence retrieval + deep model for every eligible event, including explicit abstention. |
| confidence_cascade | Fast first; upgrade when calibrated confidence <0.7, thresholds validated before test. |
| random_cascade | Seeded hash of event ID; fixed validation-chosen escalation rate/budget, no future test-count matching. |
| vow_cascade | Fast first; predict incremental net action utility from pre-routing features, subtract incremental compute cost, upgrade only if positive. Start with a frozen linear scorer; train coefficients only on adequately covered training counterfactuals. |

All semantic paths emit a target market, YES/NO/NONE, expected YES price at the common exit horizon, confidence, input evidence IDs, input cutoff, completion time and compute cost. Settlement probability is a separate optional field and must not substitute for expected short-horizon price. Every target must belong to the as-of candidate set. A caller cannot forge earlier completion to obtain an earlier snapshot.

Initial conversion: fixed 10-share order, 2-cent minimum predicted edge over current ask plus explicit estimated fee allowance; available capital $1000, maximum one open position per condition, long token purchases only. Quantity/edge/capital are shared across arms. No-trade and market-only baselines are exempt from semantic confidence requirements but use the same execution eligibility and capital checks.

VOW features: fast confidence/edge, retrieval margin, candidate count, source-time age, known spread/depth, past volatility and expected extra tool cost/latency. Future books, deep outputs and labels cannot enter the route. Add no-extra-search and latency-zero ablations to separate information, reasoning and waiting. Report same-snapshot fraction and snapshot-crossing distribution.

## Snapshot execution

REST polling is the primary track; WS is independently reported. No merged continuous state. At or after order arrival, inspect the first observed same-source snapshot, not the first hindsight-profitable/valid snapshot. Malformed/crossed/conflicting first observations reject the attempt; one-sided books support only the order side with displayed liquidity; later retry is only a new policy action. Maximum wait 900s (300/1800 sensitivities), with order expiry no later than exit due time. Execute against observed asks for entry and bids for exit using depth limits and minimum order size. No carry-forward book fill, passive queue model or YES/NO synthetic liquidity.

The displayed snapshot is an execution scenario, not guaranteed live fill. Fees are explicit notional-bps stress scenarios (0/20/100 bps), not asserted historical Polymarket fee schedules. Unknown historical fees disable claims of historically accurate net PnL. Share consumption within a snapshot prevents duplicate simulated liquidity use. Never reserve an order using future exit-book knowledge.

Missing exit keeps an open/censored position and locked capital; no fabricated zero PnL or capital refund. Report realized cash PnL, open exposure and conservative equity bounds; point drawdown only where marked values are observed under the stated age rule. Settlement disabled without verified outcomes.

## Metrics and inference

Trading: gross/fee/compute/net realized PnL, return on deployed capital, turnover, spread and depth costs, fill fraction, rejection reasons, open exposure, marked/bounded equity and drawdown. Never annualize a seven-day pilot into a headline Sharpe/APY.

Systems: all-event coverage, candidate coverage, abstention, invalid output rate, escalation, inference/retrieval/total latency, execution wait, cost and same-snapshot frequency. Retrieval recall/semantic precision require independent human gold; keep silver separate. Brier/ECE require verified settlement labels and are unavailable without them. Short-horizon direction accuracy uses declared price-proxy labels, not invented semantic truth.

VOW: G/W/VOW on paired complete counterfactuals, paired sample N, missingness and cluster-aware IQR/bootstrap by validated families. Portfolio contrasts remain chronological; isolated counterfactuals do not share hypothetical capital. Report selection bias from the complete-pair subset.

## Proposed first experiment (deferred)

Build the full cleaned week and export model-safe observations; run deterministic no-trade/momentum and replay fixture or externally recorded fast/deep outputs through the same engine. A fixture integration run verifies plumbing, not semantic alpha. Actual model baseline evaluation is a subsequent experiment once model versions, prompts and evidence corpus are frozen. No new provider acquisition or deployment is required for this first infrastructure release.
