# Value of Waiting: Opportunity-Aware Selective Reasoning in Prediction Markets

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-37%20passed-brightgreen.svg)](tests/)
[![Standard Library](https://img.shields.io/badge/dependencies-standard--library%20only-success.svg)](src/)

Empirical research scaffold and pilot experiment investigating the fundamental question:  
> **When is deeper semantic reasoning worth waiting for in an event-driven prediction market?**

---

## 1. Quickstart & Verified Commands

The core pipeline is self-contained and runs using only the **Python 3.11+ standard library** (no third-party runtime package dependencies required).

### 1.1 Run Test Suite
Run the 37 unit tests covering client security, response parsing, bundle construction, metrics, and deterministic outputs:
```bash
python -m unittest discover -s tests -v
```

### 1.2 Replay Pilot Experiment (Offline Mode)
Replay the full pilot analysis using the local content-addressed raw cache (does not require internet access or API credentials):
```bash
python scripts/run_pilot.py run --config config/pilot.json --output outputs/pilot --offline
```

### 1.3 Replay Order Book Audit (Offline Mode)
Replay the order book snapshot coverage audit:
```bash
python scripts/run_pilot.py audit --config config/pilot.json --output outputs/pilot --offline
```

### 1.4 Live Execution (Online Mode)
To fetch fresh data or re-audit live endpoints, supply the Findata token transiently via environment variable:
```powershell
$env:LUMID_PAT = "your_token_here"
python scripts/run_pilot.py run --config config/pilot.json --output outputs/pilot
Remove-Item Env:LUMID_PAT
```

---

## 2. Key Pilot Findings

An empirical pilot was conducted across **17 Polymarket contracts** (*"Will Elon Musk post [X] tweets from May 19 to May 26, 2026?"*) matched with **309 tweets** (260 bundles) by `@elonmusk`:

| Latency Horizon ($\Delta t$) | Clean Eligible Pairs | Updated Pairs | Updated Fraction | Median Bundle Update Rate (IQR) | Repricing ($\Delta \pi$) | Delayed State Age |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **5 seconds** | 789 | 26 | **3.3%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 292.0s |
| **10 seconds** | 787 | 36 | **4.6%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 295.0s |
| **30 seconds** | 769 | 86 | **11.2%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 291.0s |
| **60 seconds (1m)** | 760 | 111 | **14.6%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 318.5s |
| **120 seconds (2m)** | 597 | 119 | **19.9%** | 0.0% (0.0% – 0.0%) | 0.000 pts | 360.0s |
| **300 seconds (5m)** | 297 | 67 | **22.6%** | 0.0% (0.0% – 25.0%) | 0.000 pts | 491.0s |
| **600 seconds (10m)**| 180 | 68 | **37.8%** | 0.0% (0.0% – 58.8%) | 0.000 pts | 656.0s |
| **1800 seconds (30m)**| 105 | 105 | **100.0%** | 100.0% (100.0% – 100.0%) | 0.300 pts | 284.0s |

### Core Architectural Conclusions
- **Viable Reasoning Window:** The actionable latency scale is **5 to 120 seconds**. Slower models ($>10\text{ minutes}$) face severe opportunity decay, while sub-second ($<1\text{s}$) models cannot be evaluated on integer-second historical data.
- **Trade Sparsity vs. Reaction:** Lack of new trade prints at short latencies ($5\text{s}$) primarily reflects **trade sparsity and under-resolution**, not 100% preserved executable opportunity.
- **Historical Execution Limitation:** Historical L2 order-book snapshots are sparse (0 snapshots found for 34 target outcome tokens). Historical metrics must be labelled as **non-executable price-state proxies**.

---

## 3. Repository Structure

```text
d:/urops/V1/
├── config/                  # Configuration files
│   └── pilot.json           # Validated pilot configuration
├── data/                    # Data directory (raw cache is gitignored)
├── docs/                    # Architectural and methodology documentation
│   ├── data_audit.md        # Comprehensive data feasibility audit
│   ├── research_plan.md     # Mathematical formulation and full research plan
│   ├── specs/               # Implementation specifications
│   └── plans/               # Development execution plans
├── outputs/pilot/           # Committed aggregate artifacts (CSV, JSON, SVG)
├── reports/                 # Markdown research reports
│   └── pilot_summary.md     # Detailed empirical pilot report
├── scripts/                 # CLI entry points
│   └── run_pilot.py         # Pilot CLI
├── src/value_of_wait/       # Core Python package (standard library only)
│   ├── cli.py               # Argument parsing
│   ├── client.py            # Secret-safe REST client
│   ├── outputs.py           # Output writers
│   ├── parsing.py           # Response parsers & canonicalization
│   ├── pipeline.py          # Acquisition and cache replay
│   └── study.py             # Event construction and metrics
├── tests/                   # 37 unit tests
├── AGENTS.md                # Invariants and developer guidelines
└── README.md                # This file
```

---

## 4. Documentation Links

- [AGENTS.md](file:///d:/urops/V1/AGENTS.md): Developer invariants, security rules, and leakage constraints.
- [Data Feasibility Audit](file:///d:/urops/V1/docs/data_audit.md): Systematic capability and limitation assessment of Findata, EventXBench, and Polymarket/Kalshi mechanics.
- [Research Plan](file:///d:/urops/V1/docs/research_plan.md): Formal research questions, hypotheses (H1–H7), mathematical decomposition, model latency accounting, cascade variants (V0–V6), and stage gates.
- [Pilot Summary Report](file:///d:/urops/V1/reports/pilot_summary.md): Comprehensive empirical findings, latency profile table, and next research steps.
