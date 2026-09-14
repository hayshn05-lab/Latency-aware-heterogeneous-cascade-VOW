> Historical evidence only. Current decisions are maintained in CURRENT_STATUS.md and docs/research_plan_current.md. REST findings are sample-specific; the pilot does not establish a profitable window.

# Data Feasibility Assessment

**Project:** Opportunity-Aware / Latency-Aware Selective Reasoning in Event-Driven Prediction Markets  
**Date:** August 2026  
**Status:** Verified via Live API Audits and Local Replay  

---

## 1. Executive Summary

This feasibility assessment evaluates whether current data providers—principally **Findata (Lumid)** and **EventXBench**, complemented by venue documentation from **Polymarket** and **Kalshi**—can support empirical research on latency-aware prediction market reasoning.

### Key Verdict
1. **Findata REST API is functional and authenticated**, but historical coverage is **stratum-specific**. It reliably supports **KOL tweets**, **market search/metadata**, and **token-level trade series**.
2. **Polymarket condition-level candles mix YES and NO trades into single OHLC bars**, creating severe synthetic price spikes. Raw candle endpoints must **not** be used for directional probability analysis.
3. **Historical L2 order-book snapshot coverage is sparse to non-existent** for historical event windows (audit yielded 0 snapshots across 34 outcome tokens in the target May 2026 week). Consequently, **executable PnL, passive fills, and queue positions cannot be claimed from historical archives**.
4. **Timestamp resolution is integer seconds** across tweet publication and historical trade records. Sub-second (millisecond) reaction latency is **unidentifiable** without prospective synchronized receipt-time recording.
5. **EventXBench (v2)** provides rigorous point-in-time semantic linking (T2) and evidence grading (T3), but its canonical targets (T4–T6) operate at **daily** horizons. It cannot supply second/minute market reaction ground truth directly.
6. **Recommended Scope:** A **two-track research design**:
   - **Track 1 (Semantic Resolution):** Evaluate fast vs. deep model accuracy and calibration on pinned EventXBench T2/T3 benchmarks.
   - **Track 2 (Market Timing & Price-State VOW):** Evaluate empirical opportunity decay and non-executable belief-price moves on token-level Findata trade series (5s to 600s).
   - **Prospective Stage:** Deploy an SSE recorder for live L2 and receipt timestamps before making execution-aware routing claims.

---

## 2. Source-by-Source Feasibility Audit

### 2.1 Findata (Lumid API)

| Endpoint Family | Endpoint Path | Verified Parameters | Live Audit Finding | Usability Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **KOL History** | `/kols/{handle}/tweets/history` | `handle`, `since`, `until`, `limit` (max 1000) | Retrieved 309 tweets for `@elonmusk` in 7-day window. Timestamps are ISO 8601 UTC to integer seconds (`created_at`). | **Fully Usable** for signal timestamping at $\ge 1\text{s}$ resolution. |
| **KOL Search** | `/kols/tweets/search` | `q`, `since`, `until`, `limit` | Full-text search across KOL archive. | **Usable** for candidate event discovery. |
| **Market Search** | `/prediction-markets/markets/search` | `q`, `venue`, `status`, `limit`, `offset` | Paginated search (limit 1000, offset). Retrieved 200 markets for "Elon Musk post". Requires strict post-filtering on titles/windows. | **Fully Usable** with pagination and exact family matching. |
| **Market Detail** | `/prediction-markets/markets/polymarket/{condition_id}` | `condition_id` | Returns `outcomes` and `clob_token_ids` lists. Outcomes can be parallel lists or object lists. | **Fully Usable** once parsed into typed YES/NO token mappings. |
| **Trades** | `/prediction-markets/trades/polymarket/{condition_id}` | `condition_id`, `from`, `to`, `limit` (max 1000) | Returns individual executions with `ts` (integer seconds UTC timestamp), `token_id`, `price`, `size`, `side`. | **Fully Usable** for token-level belief state reconstruction. |
| **Candles** | `/prediction-markets/candles/polymarket/{market_id}` | `interval` (1, 5, 15, 60, 1440), `from`, `to` | **Critical Trap:** OHLC bars aggregate trades from *both* YES and NO tokens without outcome separation, distorting prices (e.g. YES at 0.10 and NO at 0.90 produce high=0.90, low=0.10 in the same candle). | **NOT Usable** for directional probability series. Must use token trades instead. |
| **Order Book** | `/prediction-markets/orderbook/polymarket/{asset_id}` | `asset_id`, `from`, `to`, `limit` | Historical snapshots returned 0 rows for target tokens during the May 2026 window. Only recent/live markets have snapshots. | **NOT Usable for Historical Execution**. Reverts to non-executable price proxy. |
| **SSE Stream** | `/prediction-markets/stream` (live) | Streaming SSE | Real-time trades and book delta stream. | **Recommended for Prospective Recording**. |

---

### 2.2 EventXBench (Benchmark & Alignment Framework)

| Component | Canonical State (July 2026 v2) | Hosted State (Hugging Face) | Research Applicability |
| :--- | :--- | :--- | :--- |
| **T1: Topic Clust.** | Unsupervised event clustering | Legacy splits | Secondary baseline. |
| **T2: Market Linking** | Pinned release (`t2.gold.r3.contextual.v1`). Frozen candidate sets, explicit `NONE`, point-in-time constraints. | Legacy schema | **Primary Semantic Benchmark** for fast vs. deep linking accuracy, MRR, and `NONE` detection. |
| **T3: Evidence Grade** | Human-adjudicated gold audit pool + silver training pool. Multi-grade ordinal scale. | Merged splits | **Primary Semantic Benchmark** for quadratic-weighted kappa ($\kappa_w$) evidence evaluation. |
| **T4–T6: Forecasting** | Daily resolution (1-day, 3-day, 7-day price direction / distribution). | Intraday legacy fields (`delta_2h`) | **Not applicable for sub-hour latency study**. Canonical v2 targets are daily; legacy intraday fields must not be mixed into v2 evaluation. |

---

### 2.3 Polymarket & Kalshi Venue Mechanics

- **Polymarket CLOB:** Binary outcome tokens ($T_{\text{YES}} + T_{\text{NO}} = \$1.00$). Orders match against discrete tick sizes (typically \$0.01 or \$0.001). Executable price requires crossing the spread (buying at ask, selling at bid) and accounting for available depth across price levels.
- **Kalshi:** Direct CFTC-regulated exchange. Ticker-based contracts (e.g. `KXBTCD-...`). Trades and candles available via Findata Kalshi endpoints.
- **Venue Mechanics Role:** Venue documentation defines market rules, fee structures, and order lifecycle constraints. It serves as a mathematical/mechanical reference rather than a separate raw data repository.

---

## 3. Critical Data Quality & Methodological Findings

### 3.1 The Polymarket Candle Outcome-Mixing Trap
When querying `/prediction-markets/candles/polymarket/{condition_id}`, the provider's backend aggregates executed trades across all outcome token IDs associated with the condition. In a binary market:
- If a YES token trades at \$0.15 and a NO token trades at \$0.85, the candle records Open=\$0.15, High=\$0.85, Low=\$0.15, Close=\$0.85.
- This creates an artificial 70-point volatility bar that does not represent any single token's price movement.
- **Solution:** Our pipeline bypasses condition-level candles entirely. It queries `/prediction-markets/trades/polymarket/{condition_id}`, maps each execution's `token_id` to either YES or NO using `/prediction-markets/markets/polymarket/{condition_id}`, and canonicalizes all trades to a unified YES-probability scale:
  $$\pi_{\text{YES}} = \begin{cases} P_{\text{trade}} & \text{if token is YES} \\ 1 - P_{\text{trade}} & \text{if token is NO} \end{cases}$$

### 3.2 Historical L2 Order Book Sparse Coverage
An audit of historical order books for 17 Polymarket markets (34 outcome tokens) during May 19–26, 2026 yielded **0 historical snapshots**.
- **Implication:** Historical prediction market archives primarily retain trade logs, not dense L2 order books.
- **Consequence:** Claims of executable PnL, slippage modeling, queue priority, or passive maker fills cannot be made on historical data without fabricated assumptions.
- **Methodological Rule:** All historical market reaction metrics must be explicitly labelled **"non-executable price-state proxies"** or **"belief-state repricing"**, never trading profit or realizable PnL.

### 3.3 Timestamp Semantics & Precision Boundaries
Both Findata tweet `created_at` and trade `ts` fields provide **integer-second resolution** (zero fractional digits).
- **Millisecond Resolution:** Completely unidentifiable from historical data. Any model response grid spaced at 0.1s, 0.5s, or sub-second intervals is interval-censored noise.
- **Inference Latency Horizon:** The empirically viable range for event-driven reasoning is **5 seconds to 600 seconds (10 minutes)**. Beyond 10 minutes, market opportunity decays substantially and 30 minutes acts merely as a terminal marking endpoint.

---

## 4. Identifiability Matrix

The following matrix formally establishes what empirical claims are scientifically identifiable under each data tier:

| Target Measure / Claim | Data Tier P0 (Findata Historical Trades) | Data Tier E1 (EventXBench Canonical) | Data Tier H1 (Broad Findata Sample) | Data Tier R1 (Prospective SSE Recorder) |
| :--- | :---: | :---: | :---: | :---: |
| **Fast vs Deep Linking Accuracy** | ❌ (Mechanical count) | ✅ (T2 Benchmark) | ✅ (Human gold pool) | ✅ |
| **Evidence Grading Kappa ($\kappa_w$)** | ❌ | ✅ (T3 Benchmark) | ✅ (Human gold pool) | ✅ |
| **Sub-second / Millisecond Latency** | ❌ (Integer seconds) | ❌ (Daily) | ❌ (Integer seconds) | ✅ (With sync clock) |
| **Seconds-to-Minutes Trade Repricing** | ✅ (Descriptive) | ❌ | ✅ (Descriptive) | ✅ (Operational) |
| **Non-Executable Remaining Move Proxy** | ✅ | ❌ | ✅ | ✅ |
| **Marketable Order Executable Replay** | ❌ (No L2 snapshots) | ❌ | ❌ (Unless L2 passes) | ✅ (Dense L2 required) |
| **Passive Limit Order Queue Simulation** | ❌ | ❌ | ❌ | ❌ (Needs order lifecycle) |
| **Realized Trading PnL / Alpha** | ❌ | ❌ | ❌ | ❌ (Needs execution) |
| **Causal Tweet Impact on Market** | ❌ (Observational) | ❌ | ❌ (Observational) | ❌ (Needs causal design) |

---

## 5. Required Architectural Safeguards

To prevent research invalidity and silent data corruption:
1. **Content-Addressed Cache:** All REST responses must be cached locally with SHA-256 digests of the canonical JSON payload, enabling fully offline, deterministic test replay.
2. **Credential Redaction:** The API token (`LUMID_PAT`) must only exist in transient runtime memory. Client error messages, exception tracebacks (`__cause__`), request logs, and committed artifacts must scrub all authentication headers.
3. **Strict Outcome Validation:** Markets with ambiguous token-outcome mappings (e.g. missing outcome names or non-binary structures) must be strictly excluded with logged reasons.
4. **Staleness Tracking:** Every market state lookup must record `delayed_age_seconds` (elapsed time since last trade). States older than the registered staleness threshold (900s) must be flagged as missing.
5. **No Lookahead in Bundles:** Multi-tweet clusters cannot be collapsed into retrospective bundles without explicitly charging the confirmation inactivity gap (e.g. 60s) as system latency.
