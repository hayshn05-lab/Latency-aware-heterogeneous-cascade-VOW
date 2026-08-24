# AGENTS.md — Research & Development Invariants

Welcome to the **Opportunity-Aware / Latency-Aware Prediction Market Research Repository**.  
This document defines mandatory protocols, methodological invariants, data contracts, and coding rules that all future AI coding agents and human researchers **must strictly follow**.

---

## 1. Core Research Objective & Scientific Framing

### 1.1 Central Research Question
> **When is deeper semantic reasoning worth waiting for in an event-driven prediction market?**

Do **not** treat the mere construction of a two-stage cascade as the primary scientific novelty. The core scientific contribution is formalizing and estimating the **Value of Waiting ($\text{VOW}$)**:
$$\text{VOW}_i = G_i + W_i$$
- **Semantic / Action Gain ($G_i$):** Counterfactual improvement in decision quality from deeper reasoning, evaluated at the fast model's completion time.
- **Wait Cost ($W_i$):** Market opportunity lost during the additional reasoning latency, holding the deep action fixed.

A latency-aware router must escalate to deep reasoning if and only if $\mathbb{E}[\text{VOW}_i \mid x_i] > c_{\text{compute}}$.

---

## 2. Verified Empirical Assumptions & Current Findings

1. **Findata API REST Capabilities:**
   - Reliable for KOL tweet archives (`/kols/{handle}/tweets/history`) and search.
   - Reliable for market metadata search and token-level trade logs (`/prediction-markets/trades/polymarket/{condition_id}`).
   - **Condition-level candles are corrupted** because Polymarket candles mix YES and NO trades into unified OHLC bars. **Never** use condition-level candles for directional probability series.
2. **Order Book L2 Snapshots:**
   - Historical L2 order-book snapshots are **sparse to non-existent** (an audit of 17 markets / 34 outcome tokens during May 2026 returned **0 historical snapshots**).
   - **Never** claim executable PnL, slippage modeling, or passive queue fills on historical trade logs.
3. **Timestamp Semantics & Resolution:**
   - Source tweet timestamps and trade logs have **integer-second resolution** (zero fractional digits).
   - Millisecond ($<1\text{s}$) effects are **unidentifiable** from historical feeds.
4. **Empirical Latency Regime:**
   - The relevant decision horizon spans **5 seconds to 600 seconds (10 minutes)**. Beyond 10 minutes, market repricing is largely complete; 30 minutes acts solely as an outcome marking horizon.

---

## 3. Strict Point-in-Time & Leakage Rules

Every agent modifying or writing data pipelines must enforce these rules without exception:

1. **No Future Leakage in Candidate Sets:**
   Candidate markets presented to a model at decision time $t_0$ must have been active, open, and indexed **before $t_0$**. Never generate candidate sets using retrospective market lists created after $t_0$.
2. **Strictly As-Of Market States:**
   Market states at decision timestamp $t$ must use trades executed **strictly at or before $t$**.
3. **No Retrospective Bundling Lookahead:**
   When grouping multi-tweet bursts into bundles with an inactivity gap (e.g. 60s), an online agent cannot know a tweet is the "last" without waiting the gap. Therefore:
   - Either issue decisions immediately per-tweet on receipt (recommended);
   - Or charge the full 60-second debounce gap as system latency.
4. **Grouped Temporal Splits:**
   Train, validation, and test splits must be temporally partitioned with an embargo buffer. All contracts within the same market family (e.g. all 17 brackets of an Elon tweet count market) must reside entirely on one side of a split.
5. **Sealed Test Sets:**
   Thresholds, prompts, hyperparameters, and router models must be frozen on the validation split before running on test. Model-runner code must never access ground-truth test labels.

---

## 4. Data-Source Conventions & Identifier Mapping

### 4.1 Identifiers
- `condition_id`: 64-character hex string (e.g. `0x08fe7d...`), the primary identifier for Polymarket markets.
- `clob_token_id` / `asset_id`: Big-integer string (e.g. `11546208...`), identifying the specific outcome token (YES or NO).
- `market_id`: Identifier alias used in search results; in Polymarket, typically equals `condition_id`.
- `tweet_id`: Unique identifier for source KOL posts.

### 4.2 YES-Probability Canonicalization
All trades must be canonicalized to YES outcome probability ($\pi_{\text{YES}} \in [0.0, 1.0]$):
$$\pi_{\text{YES}} = \begin{cases} P_{\text{trade}} & \text{if token is YES} \\ 1.0 - P_{\text{trade}} & \text{if token is NO} \end{cases}$$

### 4.3 Data Sources & Boundaries
- **Findata (Lumid):** The primary data provider for KOL tweets, market metadata, token trades, and real-time SSE streams.
- **EventXBench:** The primary benchmark framework for point-in-time semantic candidate linking (T2) and human-gold evidence grading (T3). Use pinned July 2026 v2 releases.
- **Polymarket Documentation:** Mathematical and mechanical reference only (fees, tick size, order matching). Do not treat as an unverified observational data source.

---

## 5. Security & Credential Invariants

- **Zero Secret Exposure:** The API token (`LUMID_PAT`) must **never** be hardcoded, written to files, logged in output artifacts, included in Git commits, or echoed in error tracebacks.
- **Sanitized Client:** `FindataClient` must sanitize request logs and error messages. Exception chaining (`raise ... from error`) must not preserve secret-bearing upstream exceptions.
- **Offline First:** All core analysis and tests must run in `--offline` mode using cached fixtures without requiring network access or credentials.

---

## 6. Directory Structure & Data Placement Rules

```text
d:/urops/V1/
├── config/                  # Configuration JSON/YAML files (reproducible parameters)
│   └── pilot.json           # Validated pilot configuration
├── data/                    # Data directory (split by lifecycle stage)
│   ├── raw/                 # Ignored content-addressed raw API responses (data/raw/findata/)
│   └── interim/             # Normalized, point-in-time aligned intermediate tables
├── docs/                    # Architectural and methodology documentation
│   ├── data_audit.md        # Comprehensive data feasibility audit
│   ├── research_plan.md     # Mathematical formulation and full research plan
│   ├── specs/               # Implementation specifications
│   └── plans/               # Development execution plans
├── outputs/                 # Committed deterministic aggregate outputs
│   └── pilot/               # Pilot results (CSV, JSON, SVG, findings MD)
├── reports/                 # Markdown research reports and summaries
│   └── pilot_summary.md     # Detailed pilot report
├── scripts/                 # CLI entry points
│   └── run_pilot.py         # Pilot audit and run CLI
├── src/value_of_wait/       # Core Python package (standard library only for core)
│   ├── __init__.py
│   ├── cli.py               # Argument parsing and command dispatch
│   ├── client.py            # Secret-safe retrying REST client
│   ├── outputs.py           # Deterministic artifact writers (CSV, JSON, SVG)
│   ├── parsing.py           # Tolerant response parsing & YES/NO mapping
│   ├── pipeline.py          # Acquisition, cache management & orchestration
│   └── study.py             # Event construction, delay profiling & metrics
├── tests/                   # Unit test suite (unittest, standard library)
│   ├── test_cli.py
│   ├── test_client.py
│   ├── test_outputs.py
│   ├── test_parsing.py
│   ├── test_pipeline.py
│   └── test_study.py
├── pyproject.toml           # Package definition (Python >= 3.11)
├── README.md                # Repository overview and quickstart
└── AGENTS.md                # This file (developer & agent invariants)
```

---

## 7. Testing & Verification Expectations

1. **Standard Library Core:** The core `value_of_wait` package must rely strictly on Python 3.11+ standard library modules (`json`, `pathlib`, `urllib`, `hashlib`, `unittest`, `re`, `datetime`).
2. **TDD Discipline:** When adding features or fixing bugs, write a failing unit test first, verify failure, implement the fix, and verify green.
3. **Full Suite Verification:** Before completing any task, run:
   ```bash
   python -m compileall -q src scripts tests
   python -m unittest discover -s tests -v
   ```
4. **Deterministic Output:** Artifact writers must produce byte-deterministic output (sorted dictionary keys, formatted floats, stable SVG markup).

---

## 8. What Agents Must NEVER Silently Assume

1. **NEVER assume last trades represent executable prices.** Last trades do not reflect bid-ask spreads, depth exhaustion, or maker queue delays. Label them as *"non-executable price-state proxies"*.
2. **NEVER assume historical order books are available.** Always run an explicit audit; if snapshots are 0, state that execution modeling is unidentifiable on that stratum.
3. **NEVER assume condition-level Polymarket candles have valid YES prices.** They mix YES and NO trades. Always query token-level trades and canonicalize using outcome token IDs.
4. **NEVER assume second-resolution timestamps can evaluate sub-second latency.** 0.1s or 0.5s grids on 1-second timestamps are invalid noise.
5. **NEVER equate topical similarity with causality.** Tweets and market moves may both react to an exogenous breaking event.
6. **NEVER log or commit credentials.**
7. **NEVER treat a multi-tweet burst as an instantaneous bundle without charging the debounce inactivity gap.**
8. **NEVER treat missing trade updates at $\Delta t = 5\text{s}$ as "100% preserved opportunity."** In sparse markets, lack of trade prints represents under-resolution / trade inactivity, not guaranteed executable liquidity.

---

## 9. Experiment Recording & Reproducibility Protocol

- Every experiment must be runnable from a CLI command referencing a version-controlled config file under `config/`.
- Every generated output directory must include a `data_manifest.json` recording endpoint paths, parameters, response SHA-256 digests, row counts, and retrieval timestamps.
- Summary JSON files must report sample sizes ($N$), coverage fractions, timestamp precision classification, and cluster-aware interquartile ranges (IQR).
