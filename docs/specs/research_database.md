# Research database and acquisition contract

## Why SQLite

The first release is a single-researcher, append-oriented local dataset. SQLite supplies transactional imports, indexed temporal joins and SQL inspection without a server or third-party core dependency. Raw JSONL remains the portable source of truth. Large future releases can partition raw materializations by window and migrate analytical projections to another store without discarding provenance.

## Schema version 1

`records`: kind, row_sha256, entity_id, condition_id, asset_id, source_time, ingest_time, source, payload. The primary key is (kind,row_sha256). Views `markets`, `tweets`, `trades`, `books` select each kind. Indexes cover kind/asset/time, kind/condition/time and kind/entity.

`record_sources`: (kind,row_sha256,query_sha256), linking every imported version to its acquisition query. `schema_version` records the format version. Full original projected rows remain JSON in payload; source/ingest times used in indexes are normalized to fixed-width UTC. Missing/invalid/naive times remain NULL, not invented.

Identical full rows are imported once; different revisions of the same tweet/market/trade are preserved. Provider trade_id alone is not a deduplication key. Import is transactional per page and rerunnable. Additional windows/configs can share the database; release summaries must distinguish window-specific acquisition counts from accumulated database totals.

## Acquisition

A frozen config specifies endpoint SQL projections, predicates, ordering, page size, UTC window, cache, database, release and audit settings. `/retrieve` materializes JSONL; the client validates returned row counts and caches exact response bytes by SHA-256. Each query record stores SQL, endpoint, format, row count and retrieval timestamp. Offline mode verifies hashes and refuses missing queries without touching credentials or network.

The initial market predicate is scheduled overlap; it includes unknown start_date but excludes missing end_date. It may omit a traded market with stale or missing schedule data, and it is not the historical eligible universe. Report identifier coverage against the collected trade/book tapes. Fields such as active/closed, events, description and fee schedule are current snapshots and must not be exposed to historical model decisions without provenance proving availability.

The service is a live warehouse, not a snapshot-isolated multi-request transaction. Stable ordering and source-count reconciliation catch truncation, but equal counts do not prove no source revision occurred. A release represents recorded query materializations at their individual retrieval times. Append revisions rather than silently overwriting evidence.

## Replay-readiness audit

Read-only analysis counts mapping failures, valid/empty/malformed/crossed books, source-specific coverage, token cadence and ingestion lag. It evaluates both outcomes over frozen offsets using deterministic sampled post timestamps. This cross-product is explicitly structural and contains no inferred semantic gold links.

Use strict as-of selection, reject conflicting latest states, and compare exchange-clock with provider-ingested books. Missing metadata history, semantic labels, stream continuity, fees/exits/size and measured signal availability prevent an H2 strategy claim even when some clock-grid states pass. Trades remain non-executable price-state proxies.

The manifest and JSON/CSV audit outputs are reviewable aggregate evidence; raw content and databases remain ignored. Test labels and credentials are not database inputs for the weekly acquisition.
