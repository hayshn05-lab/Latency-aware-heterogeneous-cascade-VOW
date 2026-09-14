# Phase-one design handoff

Closed scope, 2026-09-14: the user requested completing the design and wrapping up the goal, explicitly deferring all experiments and baseline runs. This supersedes the earlier instruction to finish and run the entire experimental pipeline during this goal.

## Completed and evidenced

1. Read the original direction note and reviewed primary sources. Saved research direction, paper-derived adaptations and concrete baseline/cascade/metric design.
2. Updated AGENTS and current navigation; archived September 13 plan/status and marked the earlier weekly diagnostic as historical. Preserved source observations, original reference documents and pilot artifacts. Existing legacy entrypoints stay in their archive folder because reproducible older releases/tests depend on them.
3. Verified source-separated cadence: REST approximately 300 seconds, WS heterogeneous. Avoided equating subscription count with the observed paired-book cohort or inferring a gap's cause.
4. Completed the cleaning job already in progress: versioned p1 tables and release `9a8a8df08bc79059a3d8f05f`, with source/config/code/table fingerprints in data/releases/phase1_v1/data_manifest.json. It is a conditional research cohort, not strict H2. The earlier materialization remains as a versioned development record; every reader must select release_id explicitly.
5. Preserved implementation drafts with behavioral tests for receipt semantics, side-specific books, lifecycle intervals, fingerprint verification, as-of context, selective invocation, snapshot expiry, cash accounting and counterfactual decomposition. No actual-data strategy/model experiment was executed.

## Deferred; not claims of completion

- Freeze and enforce grouped temporal/embargo splits, connected event-family identities and sealed evaluation artifacts.
- Finish robust input/config validation and comprehensive rejection accounting, including invalid/missing model trajectories, costs, exposure/expiry and cross-arm fairness.
- Verify all baselines and the cascade through the common harness against real data when authorized. The runner currently accepts development mode only; it must not be used to claim sealed-test evidence.
- Integrate evaluator-only semantic/settlement labels and full calibration/recall metrics where labels exist; null placeholders are not implemented scores.
- Add a CLI for paired VOW evaluation, validated router fitting and budget-matched comparisons. Current VOW scorer coefficients are externally supplied; no router has been trained.
- Complete independent cleaned-database reconstruction, full derived-table integrity checks and final pipeline freeze after implementation review. Stored table hashes and unit-test idempotence are available; they do not replace an independent full-data rebuild.
- Resolve historical metadata proofs and fee semantics before historical executable claims; retain conditional simulation otherwise.

## Next authorized work should start here

Read the experiment draft and pipeline status, review existing phase1 modules, then finish the deferred implementation/verification before requesting or conducting model studies. Do not rerun old acquisition or delete raw data simply to start a new experiment.

## Closure verification

Compilation passed and all 81 unit/integration tests passed. The final release table counts and cleaning code hashes were checked against the database/manifest; its source fingerprints match the previously verified weekly inputs. Active local document links resolve and git diff --check passes. These checks do not include actual-data baseline/model runs or independent full cleaned-database reconstruction.
