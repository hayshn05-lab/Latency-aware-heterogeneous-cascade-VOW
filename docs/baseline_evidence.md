# Baseline evidence and adaptations

Checked 2026-09-14 against primary sources. This is a design review, not a claim to reproduce authors' datasets or reported returns. Versions below pin the cited papers; implementations need their own revision pins before exact replication.

| Source | Verified scope | Use and deliberate departure |
|---|---|---|
| [TimeSeek v1](https://arxiv.org/html/2604.04220v1), sections 5.1/5.6 | Search/no-search forecasting; defer/predict/search is a proposed gate and future work | Market probability forecast, fast-only and always-search controls. Our trading gate is new; not an implemented TimeSeek reproduction. |
| [PolyBench v1](https://arxiv.org/html/2604.14199v1), sections 3/4 | Confidence threshold 0.6; depth sweep and settlement-based confidence-weighted invested-capital return; skipped trades excluded in its conditional scoring | Always-deep adaptation under our shared sizing/exits/costs. Retain all attempts and report abstention. Do not transplant settlement confidence as expected 30-minute return or annualize the one-week pilot. |
| [PredictionMarketBench v1](https://arxiv.org/html/2602.00133v1), sections 2/3; [authors' repository](https://github.com/oddpool/PredictionMarketBench) | Deterministic Kalshi episode harness with lifecycle, execution and agent interfaces | Common replay architecture and market-only controls. Polymarket sparse snapshots do not reproduce Kalshi continuous/maker semantics. Momentum is explicitly a local adaptation, not a copied published algorithm. |
| [Ng et al., SSRN 5331995](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5331995), revised September 4 | Primary abstract verifies bidirectional cross-venue price discovery and heterogeneous leadership | Cross-venue baseline deferred: no matched Kalshi cohort. Detailed large-trade imbalance formula is not verified from accessible full text; do not claim an exact replication. Single-venue signed-volume proxy requires verified trade-side semantics. |
| [FrugalGPT](https://arxiv.org/abs/2305.05176) | Cost/quality-oriented LLM cascades | Add a calibrated-confidence threshold cascade; makes the novelty test selective trading value rather than merely cascading. |
| [RouteLLM v4](https://arxiv.org/abs/2406.18665v4) | Strong/weak routing using preference supervision | Related routing control; a learned quality/cost gate is optional after adequate train labels. No claim that generic preference weights measure trading utility. |

[Prediction Arena](https://arxiv.org/abs/2604.07355) is related work, not evidence of our data's cadence or execution validity. [Arbitrage Analysis](https://arxiv.org/abs/2605.00864) and [OpenMarket](https://arxiv.org/abs/2607.26245) use substantially different dense data; neither is a primary replay baseline here. OpenMarket also reports a null out-of-sample forecasting result, which argues for strong market controls rather than presumed alpha.

## Primary comparison set

No-trade; market-consensus forecast; market-only momentum; fast-only; always-deep; confidence cascade; deterministic seeded budget-matched random escalation; proposed VOW cascade. Same candidate universe, evidence cutoff, order conversion, capital and execution rules apply. An ex-post best-path oracle is an evaluator diagnostic only. Add order-flow and cross-venue controls only when their required source semantics and identifiers are verified.
