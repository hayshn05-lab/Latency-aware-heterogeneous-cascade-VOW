# Week 6 work log

Reporting date: 14 September 2026. Scope: database construction, research redesign, the latest completed goal, and the newly requested bounded platform trials.

## Research objective

Determine when additional information acquisition and semantic reasoning justify their latency and compute cost in prediction markets. The intended workflow is **receive information → discover eligible markets → interpret direction → selectively escalate → generate an action → simulate execution**. VOW = G + W separates action improvement from delay effects counterfactually; it is not an executable policy that knows the deep answer early.

## Work completed

| Stage | Work and evidence | Result / interpretation |
|---|---|---|
| Initial acquisition audit | Inspected narrow REST event windows, token mappings and historical books. | The negative result applied to that acquisition path, not to all Findata data or the research direction. |
| Source reconciliation | Distinguished REST, warehouse retrieval and EventXBench access. | Earlier authentication failure was not dataset absence. PAT-authenticated Findata SQL retrieval subsequently supported acquisition without a separate PostgreSQL password on that path. |
| Weekly database construction | Imported the UTC window `[2026-09-06, 2026-09-13)` through 461 successful SQL queries, retaining query provenance and raw response fingerprints. | SQLite contains 125,767 tweets, 412,272 market metadata records, 1,018,685 trades and 700,072 books: 2,256,796 records in total. Metadata volume is not monitored-market coverage. |
| Reproducibility | Preserved raw JSONL; linked normalized records to source queries; independently rebuilt the database offline. | Ordered fingerprints matched all four record groups; integrity, foreign-key and normalized-time checks passed. Nine preserved pilot outputs were reproduced byte-for-byte. |
| Coverage and cadence audit | Separated REST polling from WS observations; checked outcome mappings and book shape. | REST contributes 524,765 rows / 274 assets, with median gap about 300 seconds; 256 assets have exactly 2,016 weekly observations. WS contributes 175,307 rows / 524 assets with heterogeneous gaps. |
| Research redesign | Replaced unsupported seconds-scale execution claims with minute-scale, source-separated conditional snapshot simulation. | Primary cadence: five minutes; 15/30-minute sensitivities; 30/60-minute exits. No profitable reaction window has been established. |
| Cleaning and interface draft | Created versioned phase-one tables and common observation, strategy, execution and metric interfaces. | Release `9a8a8df08bc79059a3d8f05f`: 50,669 English original tweets, 388 mapped markets, 549,279 mapped books and 62,340 related trade proxies. Original records remain intact. |
| Latest goal closure | Consolidated plans, archived superseded documents, preserved the pilot, and handed off the design. | 81 tests and compilation passed in that goal. Interface code is a tested draft, not a frozen study. Experiments were deferred at the user's request. |
| This reporting task | The new request authorized two small related-work adaptations using the live model platform. | Forecast-context comparison and a four-case model cascade executed; detailed results are in [platform trials](03_platform_trials.md). No trading strategy was deployed. |

## What the data support

The prior weekly audit found 260 markets with both outcome tokens represented in books. Of 700,072 snapshots, 476,284 had both sides structurally present, 223,787 had a missing side, and one was crossed. These are structural statistics, not proof of executable fills. A single-sided book can still be usable for a particular order direction; full round-trip coverage requires further checks.

The saved Findata architecture describes approximately 240 active WSS subscriptions. This does not establish that they are exactly the 260 both-token markets, nor prove why WS observations are sparse. Five-minute polling cannot resolve an unobserved seconds-scale path.

The cleaned release contains 445 source-specific conditional eligibility rows and 722,345 token/horizon structural intervals. **Neither number is a count of semantically linked events or independently replayable strategies. Strict historical eligibility remains zero.** Current metadata cannot prove that a market was indexed and open when an old signal arrived.

Local EventXBench T2 data include 543 training links (166 human / 377 silver), plus 2,500 validation and 2,500 test rows. Training candidates are preset, not a live discovery process; known training dates end in June 2026, before the September warehouse week. Upstream revision provenance still needs pinning. These files do not establish September event–market overlap.

## Next bounded work

1. Freeze task definitions, candidate-discovery timing, labels and embargoed family splits before comparative experiments.
2. Validate the draft runner against real records, including unsuccessful actions, censored exits, capital locking and source-specific availability.
3. Establish archived evidence retrieval and outcome labels; use price proxies only for non-executable diagnostics.
4. Measure incremental accuracy, latency and token/currency cost first; evaluate conditional trading outcomes only after execution assumptions are validated.

The full derived-table rebuild, strict historical metadata proof and full experiment integration remain pending. The reporting trials do not close these gaps.

## Repository evidence

- [Current status](../CURRENT_STATUS.md) and [research plan](../docs/research_plan_current.md)
- [Workspace map](../docs/workspace_map.md), including preserved raw data and reference documents
- [Phase-one specification](../docs/specs/phase1_experiment.md) and [execution handoff](../docs/plans/phase1_execution.md)
- [Cleaning manifest](../data/releases/phase1_v1/data_manifest.json)

The original reporting task added three Markdown reports; trial requests and responses were handled in memory. A subsequent request added standalone reproduction scripts and a usage guide in this folder.
