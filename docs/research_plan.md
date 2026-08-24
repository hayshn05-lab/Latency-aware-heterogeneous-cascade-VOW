# Research Plan: Opportunity-Aware Selective Reasoning in Prediction Markets

**Research Question:** *When is deeper semantic reasoning worth waiting for in an event-driven prediction market?*  
**Date:** August 2026  
**Status:** Scaffold Specification & Supervisor Decision Document  

---

## 1. Research Motivation & Core Formulation

Prediction markets represent dynamic aggregations of forward-looking public beliefs. When external signals (such as news events, official statements, or influential tweets) break, market participants face a fundamental trade-off:
- **Fast, shallow reasoning** (e.g. lightweight LLMs, keyword matching, or frozen embedding retrieval) can identify potential market-event associations in sub-second or seconds-scale latency, capturing pricing misalignments before other participants react. However, shallow reasoning suffers from misinterpretations, hallucinations, candidate mismatch, and poor handling of non-relevant (`NONE`) events.
- **Deep, deliberative reasoning** (e.g. large reasoning models, chain-of-thought, or multi-agent verification) achieves higher evidence-grading accuracy and subtle context disambiguation. However, the additional latency ($5\text{s}$ to $120\text{s}+$) means that market prices may have already adjusted by the time the deliberative decision is available.

### 1.1 Mathematical Formulation of Value of Waiting ($\text{VOW}$)

Let an event instance be denoted by $i$, arriving at actionable decision-ready time $t_0$.
- Let $a_{\text{fast}, i}$ and $a_{\text{deep}, i}$ denote the action chosen by the fast and deep models, respectively.
- Let $C_{\text{fast}, i}$ and $C_{\text{deep}, i}$ denote the end-to-end completion latencies from $t_0$ until a schema-valid decision is parsed.
- Let $U_i(a, t)$ denote the realized utility (or non-executable price-state proxy) of taking action $a$ against the earliest available market state at or after $t_0 + t$.

The **Value of Waiting ($\text{VOW}_i$)** is defined as the net utility difference between escalating to the deep model versus executing the fast model immediately:
$$\text{VOW}_i = U_i(a_{\text{deep}, i}, C_{\text{deep}, i}) - U_i(a_{\text{fast}, i}, C_{\text{fast}, i})$$

We decompose $\text{VOW}_i$ into two orthogonal components:
$$\text{VOW}_i = G_i + W_i$$
where:
1. **Semantic / Action Gain ($G_i$):** The counterfactual gain of the deep action over the fast action, holding latency fixed at the fast completion time:
   $$G_i = U_i(a_{\text{deep}, i}, C_{\text{fast}, i}) - U_i(a_{\text{fast}, i}, C_{\text{fast}, i})$$
2. **Wait Cost ($W_i$):** The opportunity lost due to market movement during the additional reasoning latency, holding the deep action fixed:
   $$W_i = U_i(a_{\text{deep}, i}, C_{\text{deep}, i}) - U_i(a_{\text{deep}, i}, C_{\text{fast}, i})$$

A rational latency-aware router must escalate from fast to deep reasoning if and only if the expected value of waiting exceeds the compute/monetary cost penalty $c_{\text{compute}}$:
$$\mathbb{E}[\text{VOW}_i \mid x_i] > c_{\text{compute}}$$

---

## 2. Falsifiable Hypotheses

- **H1 (Semantic Gain):** Deeper reasoning models exhibit positive paired improvement over fast models on EventXBench T2 (Accuracy@1, `NONE` F1) and T3 human-gold evidence grading ($\kappa_w$), with maximum gain concentrated in high-ambiguity, low-lexical-overlap events.
- **H2 (Decaying Opportunity):** The attainable market price opportunity following an aligned external event decays monotonically on average across increasing decision latencies ($\Delta t \in \{5\text{s}, 10\text{s}, 30\text{s}, 60\text{s}, 120\text{s}, 300\text{s}, 600\text{s}\}$).
- **H3 (Predictable Marginal Value):** Point-in-time features—including fast model confidence, top-candidate margin, lexical ambiguity, candidate pool size, and pre-event market liquidity—can predict whether $G_i > -W_i$.
- **H4 (Latency Heterogeneity):** Markets with high baseline liquidity and active trade frequency exhibit much steeper opportunity decay ($W_i \ll 0$), compressing the viable reasoning budget to $<15\text{s}$, whereas thin markets preserve opportunity over minutes ($W_i \approx 0$).
- **H5 (Router Dominance):** A latency-aware router trained on estimated $\text{VOW}$ achieves a superior Pareto frontier (utility vs. latency vs. compute) compared to always-fast, always-deep, and static confidence thresholds on held-out temporal test splits.
- **H6 (Execution Discount):** On strata where aligned L2 order-book depth is available, execution-aware utility is strictly lower than last-trade price-move proxies due to bid-ask crossing and slippage.
- **H7 (Timing Identifiability Boundary):** Sub-second latency advantages are unidentifiable from integer-second historical feeds; prospective synchronized recorders are necessary and sufficient for sub-second claims.

---

## 3. Two-Track Research Architecture

```
                                 [External Event Signal t0]
                                             |
                     +-----------------------+-----------------------+
                     |                                               |
             [Track 1: Semantics]                            [Track 2: Market Timing]
           (EventXBench T2 / T3)                               (Findata Token Trades)
                     |                                               |
           Fast Model vs Deep Model                       Opportunity Decay Grid:
           - Candidate Linking Acc@1                      5s, 10s, 30s, 60s, 120s, 300s, 600s
           - NONE / ABSTAIN F1                            - First-print latency distribution
           - Evidence Grading (Kappa)                     - Non-executable repricing proxy
           - Confidence & Margin                          - Staleness & observation age
                     |                                               |
                     +-----------------------+-----------------------+
                                             |
                                 [Joint Sample / Router]
                               - Predict Semantic Gain G_i
                               - Predict Wait Cost W_i
                               - Router Policy: Escalate if E[VOW] > Cost
```

### Track 1: Pinned Semantic Benchmark (EventXBench)
- **Dataset:** Canonical July 2026 release (`t2.gold.r3.contextual.v1` and T3 gold audit pool).
- **Task T2 (Candidate Linking):** Given tweet/event text and a point-in-time frozen candidate set of active markets (plus `NONE`), predict top-1 linked market.
- **Task T3 (Evidence Grading):** Grade the directional relevance of the event to the market on an ordinal scale $[-2, -1, 0, +1, +2]$.
- **Evaluation Metrics:** Accuracy@1, MRR, `NONE` F1, Quadratic-Weighted Cohen's Kappa ($\kappa_w$).

### Track 2: Market Timing & Opportunity Decay (Findata)
- **Dataset:** Token-level historical trades canonicalized to YES-probability.
- **Delay Horizons:** $D = \{5\text{s}, 10\text{s}, 30\text{s}, 60\text{s}, 120\text{s}, 300\text{s}, 600\text{s}\}$ ($1800\text{s}$ outcome endpoint).
- **Measures:** Updated fraction, median repricing points ($\Delta P$), delayed state age, first-print latency.
- **Constraint:** Strictly labelled as non-executable price-move proxy.

---

## 4. Model Latency Protocol & Accounting

To avoid misleading comparisons based on theoretical or advertised token rates, latency $C_{\text{model}}$ must represent **actionable end-to-end wall-clock completion time**:

$$C_{\text{model}} = t_{\text{parse\_valid}} - t_{\text{decision\_ready}}$$

Components strictly charged to model latency:
1. Local input preprocessing and prompt serialization.
2. Network transport and API provider queueing.
3. Generation / inference wall-clock duration (including internal chain-of-thought tokens).
4. Response schema validation, JSON parsing, and retry/repair attempts.

**Inference Budget Bounds:**
- Models requiring $>600\text{s}$ (10 minutes) are excluded from the event-driven cascade as empirically non-viable.
- Time-to-First-Token (TTFT) may only be used as action time if early tokens form an irrevocable, schema-valid decision.

---

## 5. Cascade & Router Policy Variants

- **V0 (Baselines):** Always-Fast (e.g. lightweight 8B model / dense retrieval), Always-Deep (e.g. reasoning LLM), No-Action / Prior.
- **V1 (Sequential Confidence Cascade):** Fast model runs first. Escalate to Deep if fast confidence score $< \tau_{\text{conf}}$ or top-2 margin $< \tau_{\text{margin}}$.
- **V2 (Latency-Aware Marginal Value Router - Primary):** Predict both expected semantic gain $\hat{G}_i(x_i)$ and expected market decay $\hat{W}_i(x_i, \tau)$. Escalate if $\hat{G}_i + \hat{W}_i > c_{\text{compute}}$.
- **V3 (Dynamic Deadline / Optimal Stopping):** Allocate variable reasoning budget (e.g. token caps 500, 2000, 8000) conditioned on market volatility and elapsed time.
- **V4 (Provisional Act-Then-Revise):** Issue fast action immediately; deep model can confirm, modify, or cancel. (Evaluated only in prospective L2 stage due to cancellation modeling requirements).
- **V5 (Parallel Race):** Fast and deep models launched simultaneously; earliest schema-valid answer accepted unless deep arrives within $\epsilon$ window.

---

## 6. Point-in-Time & Leakage Integrity Rules

1. **No Future Leakage in Candidate Sets:** Candidate markets must have been active, open, and indexed before $t_0$.
2. **Strictly As-Of Market States:** Market observations at $t_0 + \Delta t$ must use trades executed strictly before or at that timestamp.
3. **No Retrospective Look-ahead in Bundling:** If multi-tweet bursts are grouped, either decisions are made per-tweet on receipt, or the full debounce inactivity gap (e.g. 60s) must be charged as system latency.
4. **Grouped Temporal Splits:** Temporal splits with a buffer embargo between train, validation, and test. All contracts in the same market family must reside in the same split.
5. **No Test-Set Tuning:** Thresholds, hyperparameters, and router models frozen on validation split.

---

## 7. Stage Gates & Decision Framework

| Gate | Name | Criteria / Deliverable | Status |
| :---: | :--- | :--- | :---: |
| **0** | **Governance & Freeze** | Approved research questions, metrics, causal language, and license terms. | Approved |
| **1** | **Data Feasibility Audit** | REST API audit, token trade canonicalization, order-book coverage check. | **Passed** |
| **2** | **Empirical Decay Pilot** | Reproducible pilot on 17 markets / 309 tweets with clear resolution caveats. | **Passed** |
| **3** | **Semantic Benchmark** | Fast vs deep models evaluated on canonical EventXBench T2/T3 gold splits. | Next Stage |
| **4** | **Joint Sample Construction** | Human-adjudicated Findata event sample or audited EventXBench join. | Planned |
| **5** | **Latency & SLO Profiling** | End-to-end latency distributions measured under realistic concurrency. | Planned |
| **6** | **Router Evaluation** | Held-out evaluation of V1–V3 routers against Pareto baselines. | Planned |
| **7** | **Prospective SSE Recording** | Live stream recorder for dense L2 and receipt timestamps. | Planned |
| **8** | **Final Synthesis & Publication** | Comprehensive empirical paper on Value of Waiting in Prediction Markets. | Planned |
