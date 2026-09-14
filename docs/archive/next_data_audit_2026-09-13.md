# Superseded data-audit plan (2026-09-13)

This plan preceded successful PAT access to Findata /retrieve. See ../../CURRENT_STATUS.md for execution status.

The intended sequence was to verify SQL/Studio access, inspect market/trade/L2 schemas, build a time-by-market/token coverage table, and join the local T2 training data. It required query manifests, explicit truncation/timeout/access categories, and independent-family counts before model work.

Training inputs require provenance and label separation. Candidate creation timestamps do not establish historical open/indexed status. Validation/test timestamps are missing and must be supplemented without inspecting labels. Human and silver labels cannot be pooled as human gold.

A mini-join must retain mapping failures, incomplete books, stale states, time gaps and unresolved metadata. Check both outcome tokens at entry/fast/deep/exit, snapshot versus delta semantics and depth. Freeze precision targets before observing strategy utility.

Before end-to-end experiments, specify U(t), top-k retrieval, NONE, multi-market signals, signal availability, order arrival, conflicting positions and chronological family splits. Studio summaries are exploratory unless the actual queries and materialized evidence are exported.

The active weekly acquisition expands this groundwork to a complete configured time-window extract rather than treating benchmark gold markets as the live market universe.
