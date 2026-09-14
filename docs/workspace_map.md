# Workspace map

- CURRENT_STATUS.md: verified current progress and remaining work.
- docs/research_plan_current.md: sole current research plan.
- AGENTS.md: concise enduring scientific, security and engineering rules.
- config/weekly_v1.json + scripts/run_weekly.py: active weekly warehouse acquisition/rebuild.
- data/raw/findata/weekly_v1/: immutable SQL materializations and query records (ignored).
- data/interim/weekly_v1/research.sqlite: extensible local database (ignored).
- data/releases/weekly_v1/: acquisition manifest and replay-readiness aggregates.
- docs/reference/lumid/: relocated user-provided platform documents and original assets.
- data/raw/eventxbench/local_t2/: relocated original T2 inputs; data/releases/workspace_inventory_v1 holds their fingerprints.
- docs/archive/: superseded plans and the original meeting transcript. The transcript remains in its original language as source evidence.
- scripts/legacy/: retained REST replay, universe-probe and reconciliation entrypoints.
- scripts/run_pilot.py + config/pilot.json + outputs/pilot/: preserved small insight experiment. Original raw cache paths remain stable.
- config/replay_audit_*.json, config/source_reconciliation_v1.json, data/releases/replay_audit_v1/, data/releases/reconciliation_v1/: retained historical evidence with stable config/raw references.
- src/value_of_wait/ and tests/: shared tested acquisition, normalization, storage and auditing code. Legacy modules remain because their reproducible experiments and regression tests still use them.

No raw observations were deleted. Root reference/linkage directories were relocated to the data/document hierarchy. Old REST no-go reports are historical, not the active acquisition plan.

The original generated weekly database is retained at outputs/cache/weekly_v1_rebuild/original_verified.sqlite as a reversible backup. The normalized independently rebuilt database is installed at the primary path above. Immutable raw observations are unchanged.

## Phase-one design handoff

- docs/specs/phase1_experiment.md: concrete experiment draft; no run authorized at handoff.
- docs/baseline_evidence.md: primary-source review and adaptations.
- docs/specs/phase1_pipeline.md: target interface and explicit draft status.
- docs/plans/phase1_execution.md: completed work and deferred implementation.
- config/phase1_v1.json + scripts/build_phase1.py: completed versioned cleaning job.
- data/releases/phase1_v1/data_manifest.json: latest derived-table source/config/code/content fingerprints.
- src/value_of_wait/phase1_*.py + scripts/run_phase1.py: tested implementation drafts; not a validated or frozen experiment framework.
