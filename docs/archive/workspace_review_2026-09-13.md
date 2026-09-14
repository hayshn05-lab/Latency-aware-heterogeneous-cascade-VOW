# Workspace review before weekly acquisition (2026-09-13)

Historical snapshot. The review used the user-supplied bounded conversation preview, repository documents, source platform documentation, T2 file structure and existing tests. A full remote conversation reader was unavailable. No Findata reacquisition or model run occurred during that review.

Findata was not completely uncollected: data/raw held 622 files (12,738,387 bytes) of pilot and REST evidence. Systematic warehouse coverage and replayable joined data were missing. The earlier REST no-go was sample-specific; warehouse-wide H2 remained unresolved.

Local T2 files contained 543 training rows and 2,500 rows in each validation/test file. Training comprised 543 distinct tweets, 5,035 candidate entries, 1,987 candidate conditions, 402 non-null gold rows across 310 conditions, and 141 NONE rows. Labels were 166 single_human_adjudicated and 377 silver. Internal version t2.kdd.v2 did not establish the upstream revision.

Train timestamps ranged from 2025-05-08 to 2026-06-28; every training candidate had market_created_at. Validation/test lacked post_created_at. No token books or trade-direction target was provided by T2. Preset candidates omit live market discovery, and gold answers are evaluator-only data.

The pilot covered 17 sibling tweet-count contracts. At five seconds, 26/789 eligible pairs had a new trade and median delayed state age was 292 seconds. This is sparse price-state evidence, not a demonstrated profitable window. Offline 60-second bundling requires a live debounce charge.

Platform references described personal SQL credentials, Studio SQL retrieval, remote batch compute, LLM inference, and a seven-day tape backtester. Their cached descriptions were not verified service guarantees. Recorded tape/signals do not prove complete L2 or correct signal availability. A model signal must not be made readable at its earlier source-post timestamp; temperature zero alone does not guarantee reproducibility. The consulting app was unrelated to this research pipeline.

The review unified navigation and current plans, preserved raw files and historical experiments, and created a local T2 hash inventory. Compileall and all 57 then-existing tests passed. JSONL must be parsed by actual newline, not Unicode str.splitlines(), because text may contain Unicode line separators.

Subsequent execution established that the supplied PAT can directly query /retrieve; this supersedes the previous access uncertainty. Consult CURRENT_STATUS.md and the weekly release for new evidence.
