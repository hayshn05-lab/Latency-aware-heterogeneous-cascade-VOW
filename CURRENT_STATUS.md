# Current status - 2026-09-14

## Design handoff complete; experiments deferred

The user narrowed this task to completing the design and closing the goal. **Do not launch model experiments or baseline runs without a new user request.** No actual-data strategy or model evaluation was run in this task. Synthetic unit/integration fixtures only verify code behavior.

## Agreed phase-one direction

Selective additional information acquisition and reasoning, evaluated through minute-scale, source-separated snapshot simulation. Primary REST cadence is five minutes, with fifteen/thirty-minute sensitivities and thirty/sixty-minute exits. Warehouse ingest time is provenance, not real-time tweet receipt. Source-plus-feed-delay is a stated simulation assumption. Deep retrieval uses archived as-of evidence, never today's web to answer historical events.

Snapshot execution inspects the first observation after action availability within a bounded wait, respects order side, depth and expiry, and retains failed/censored attempts. This remains a conditional execution scenario. Current market metadata does not prove historical indexed/open eligibility. A verified profit window has not been established.

## Deliverables

- [Current research plan](docs/research_plan_current.md)
- [Concrete baseline/cascade experiment draft](docs/specs/phase1_experiment.md)
- [Reviewed paper evidence and adaptations](docs/baseline_evidence.md)
- [Common pipeline contract and implementation status](docs/specs/phase1_pipeline.md)
- [Final handoff and deferred work](docs/plans/phase1_execution.md)

## Work already completed before scope closure

Source-separated cadence audit confirms 524,765 REST rows / 274 assets (256 assets have exactly 2,016 weekly rows), with median gap 299.997549 seconds. WS has 175,307 rows / 524 assets and heterogeneous intervals. The saved reference's approximate 240 live subscriptions do not establish exact membership of the 260 both-token cohort.

The already-started cleaning job completed successfully. New versioned p1 tables retain 50,669 English original tweets, 388 mapped markets, 549,279 mapped book observations and 62,340 related trade proxies. There are 722,345 lifecycle-qualified token/exit-horizon structural intervals and 445 source-specific conditional eligibility rows; these are not semantic event-market links. Strict eligibility remains zero. The release ID is `9a8a8df08bc79059a3d8f05f`; see [manifest](data/releases/phase1_v1/data_manifest.json). Original records were not deleted or changed by the materializer.

Common observation/strategy/execution/metric modules and an offline runner were started and pass synthetic behavioral tests. They are **implementation drafts, not a frozen or fully verified experimental system**. Family split enforcement, comprehensive trajectory failure handling, real-data integration and full metric coverage remain future work. No baseline ranking or alpha estimate is available.

## Preservation

The weekly acquisition, raw data and insight pilot are preserved. Previous plans/status are archived under docs/archive; legacy entrypoints remain under scripts/legacy. The original direction note and user-supplied source documents remain unchanged as evidence. See [workspace map](docs/workspace_map.md).
