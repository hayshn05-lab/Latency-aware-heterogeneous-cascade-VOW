# Empirical Pilot Report: Data Feasibility and Opportunity Decay in Event-Driven Prediction Markets

**Project:** Opportunity-Aware / Latency-Aware Selective Reasoning  
**Date:** August 2026  
**Artifacts Generated:** `outputs/pilot/` (`delay_profile.csv`, `summary.json`, `latency_profile.svg`, `market_validation.csv`, `event_bundles.csv`, `first_print_latency.csv`, `orderbook_audit.csv`, `audit_summary.json`)  
**Status:** Completed & Verified via Deterministic Offline Replay  

---

## 1. Executive Summary

This pilot experiment establishes the empirical and data foundation for research on **"When is deeper semantic reasoning worth waiting for in an event-driven prediction market?"**

### Primary Takeaways
1. **Data Feasibility:** Findata (Lumid API) supports point-in-time KOL tweets and token-level Polymarket trades. However, **Polymarket condition-level candles are contaminated** (mixing YES and NO trades into single bars), and **historical L2 order-book snapshots are unavailable** (0 snapshots found across 34 target outcome tokens).
2. **Empirical Latency Regime:** The actionable decision window for event-driven prediction markets spans **seconds to minutes ($5\text{s}$ to $600\text{s}$)**. Deeper reasoning models taking $>10\text{ minutes}$ miss almost all market opportunity, while sub-second ($<1\text{s}$) advantages are unidentifiable due to integer-second timestamp resolution.
3. **Under-Resolution of Short Latencies:** In historical trade logs, only **3.3%** of clean eligible market states record a new trade print within 5 seconds, **14.6%** within 60 seconds, and **37.8%** within 10 minutes. Median state age is several minutes. Therefore, lack of a price change at $\Delta t = 5\text{s}$ primarily reflects **trade sparsity / under-resolution**, not 100% preserved executable opportunity.
4. **Research Framing:** The full study must decompose the Value of Waiting ($\text{VOW} = G_i + W_i$) using a two-track architecture: pinned EventXBench benchmarks for semantic gain ($G_i$) and Findata token trades for market opportunity decay ($W_i$).

---

## 2. Stage A: Data Feasibility Audit Findings

We conducted live API audits across all primary endpoints with transient credentials, verifying responses against OpenAPI specs:

| Data Element | Source Endpoint | Audit Findings & Identified Traps | Usability Status |
| :--- | :--- | :--- | :--- |
| **KOL Tweets** | `/kols/{handle}/tweets/history` | Verified on `@elonmusk` (309 tweets in May 19–26, 2026 window). Integer-second UTC timestamps (`created_at`). | **Usable** ($\ge 1\text{s}$) |
| **Market Search & Metadata** | `/prediction-markets/markets/search` | Paginated search (`limit=1000, offset=0..N`). 200 markets retrieved; 17 matched the target Elon Musk tweet count family exactly. | **Usable** |
| **Token-Level Trades** | `/prediction-markets/trades/polymarket/{condition_id}` | Individual executions with `ts` (integer seconds UTC), `token_id`, `price`, `size`, `side`. Correct outcome mapping required. | **Usable** |
| **Intraday Candles** | `/prediction-markets/candles/polymarket/{market_id}` | **Trap Identified:** Backend blends YES and NO executions into the same OHLC bar, generating artificial 0.10–0.90 swings. | **REJECTED** |
| **Order Book Snapshots** | `/prediction-markets/orderbook/polymarket/{asset_id}` | Audit of 34 outcome tokens yielded **0 historical snapshots** in the May 2026 target window. | **REJECTED for Hist. PnL** |
| **EventXBench Alignment** | Canonical v2 Release | T2 (market linking) and T3 (evidence grading) provide gold semantic benchmarks. Canonical T4–T6 targets are daily. | **Usable for Semantics** |

---

## 3. Stage B: Empirical Opportunity-Decay Pilot

### 3.1 Pilot Design & Dataset
- **Market Family:** 17 Polymarket contracts on *"Will Elon Musk post [X] tweets from May 19 to May 26, 2026?"* (brackets from 0–19 up to 340+).
- **Signals:** 309 tweets by `@elonmusk` during the active window, grouped into **260 event bundles** using a 60-second inactivity gap.
- **Total Observations:** $260 \text{ bundles} \times 17 \text{ markets} \times 8 \text{ horizons} = 35,360$ evaluation rows.
- **Canonicalization:** Every trade mapped to YES-probability ($\pi_{\text{YES}} = P$ for YES, $1-P$ for NO).
- **Staleness Bound:** 900 seconds ($15\text{ minutes}$). Observations where the most recent trade is older than 900s are excluded as unobservable.
- **Horizons Evaluated:** $\Delta t \in \{5\text{s}, 10\text{s}, 30\text{s}, 60\text{s}, 120\text{s}, 300\text{s}, 600\text{s}, 1800\text{s}\}$.

### 3.2 Key Quantitative Results

| Horizon ($\Delta t$) | Clean Eligible Pairs | Updated Pairs | Updated Fraction | Median Bundle Update Rate (IQR) | Median Repricing Points ($\Delta \pi$) | Median Delayed State Age |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **5 seconds** | 789 | 26 | **3.3%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 292.0s |
| **10 seconds** | 787 | 36 | **4.6%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 295.0s |
| **30 seconds** | 769 | 86 | **11.2%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 291.0s |
| **60 seconds (1m)** | 760 | 111 | **14.6%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 318.5s |
| **120 seconds (2m)** | 597 | 119 | **19.9%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 360.0s |
| **300 seconds (5m)** | 297 | 67 | **22.6%** | 0.0% (0.0% – 25.0%) | 0.000 pts | 491.0s |
| **600 seconds (10m)**| 180 | 68 | **37.8%** | 0.0% (0.0% – 58.8%) | 0.000 pts | 656.0s |
| **1800 seconds (30m)**| 105 | 105 | **100.0%** | 100.0% (100.0% – 100.0%) | 0.300 pts | 284.0s |

*(Note: Data from `outputs/pilot/delay_profile.csv`. Updated fraction represents the proportion of clean eligible market-bundle pairs with at least one new trade print strictly between decision time and decision time + $\Delta t$.)*

### 3.3 Visual Latency Profile
The generated vector artifact `outputs/pilot/latency_profile.svg` illustrates the unsmoothed update fraction across numeric delays, displaying descriptive cluster-level interquartile ranges (IQR across bundles) rather than assuming iid row independence.

---

## 4. Stage C: Architectural Implications for Cascade & Router Design

1. **Relevant Latency Regime:** The empirical trade frequency shows that the viable reasoning budget for prediction markets is **5 to 120 seconds**. Slower deliberative pipelines (e.g. 5–10 minutes) face substantial decay ($W_i \ll 0$), while hour-scale models are entirely non-viable.
2. **Trade Sparsity vs. Reaction:** In low-volume bracket contracts, trades do not print every second. A fast model does not always face immediate competition from high-frequency bots, giving reasoning models a window of tens of seconds to minutes to act before price discovery completes.
3. **Router Objective:** A router should not simply predict "will the deep model be more accurate?", but whether the expected semantic gain exceeds the market movement during the deep model's measured latency:
   $$\mathbb{E}[\text{VOW}_i \mid x_i] = \mathbb{E}[G_i \mid x_i] + \mathbb{E}[W_i \mid x_i, \tau_{\text{deep}}] > c_{\text{compute}}$$
4. **Staleness-Aware Routing:** Point-in-time features must include pre-event market state age (`delayed_age_seconds`) and recent trade intensity. Highly active contracts decay rapidly, demanding fast models or immediate execution; thin contracts permit deeper reasoning.

---

## 5. Methodological & Alignment Limitations

- **Mechanical vs. Semantic Alignment:** The pilot used tweet-count markets where every tweet is mechanically relevant. In real-world news/KOL events, semantic alignment is non-trivial: models must filter irrelevant signals (`NONE`) and disambiguate candidate contracts.
- **Look-Ahead in Multi-Tweet Bundles:** Retrospective bundling groups tweets within 60s. In live production, an agent cannot know a tweet is the "last" in a burst without waiting the full 60-second debounce gap.
- **Non-Causal Attribution:** Price movements following a tweet may reflect concurrent external news or continuous drift rather than tweet alpha.
- **Non-Executable Proxy:** Last-trade prices do not reflect bid-ask spreads, available depth, or slippage.

---

## 6. Actionable Next Research Steps

1. **Freeze Supervisor Decisions:** Sign off on research hypotheses H1–H7 and the identifiability matrix in `docs/research_plan.md`.
2. **Execute Track 1 (Semantic Benchmark):** Benchmark fast models (e.g. 8B / dense retrieval) vs. deep reasoning models on EventXBench T2/T3 gold splits to establish empirical $\Delta_{\text{sem}}$ distributions.
3. **Construct Joint Sample:** Build a human-adjudicated Findata event sample with point-in-time frozen candidate sets.
4. **Deploy Prospective SSE Recorder:** Record live Findata SSE streams with synchronized monotonic receipt clocks to capture dense L2 depth for true execution replay.
