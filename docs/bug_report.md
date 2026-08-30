# Lumid Studio / FinData Bug Report

**Date:** 2026-08-30  
**Context:** Event-driven prediction market research project, read-only API & catalog audit  
**Affected services:** Lumid Studio / FinData REST API / PostgreSQL Catalog  

---

## Summary

The FinData REST API and Lumid Studio database are broadly operational, hosting over 6.2 billion rows of equity OHLCV data, 19.4+ million prediction market trades, and 210+ million orderbook snapshots. However, several critical catalog inconsistencies, schema mismatches, table naming ambiguities, and candle aggregation flaws undermine data discoverability, point-in-time reconstruction, and research reproducibility.

Below is the verified inventory of bugs, data traps, and documentation issues.

---

### LUMID-001 — `news.articles` schema mismatch

**Severity:** High  
`/catalog/tables/news/articles/schema.json` reports **16 columns**, while `information_schema.columns` reports **22**.  

**Missing catalog fields:**  
`id`, `ingest_ts`, `source`, `source_endpoint`, `source_run_id`, `search_tsv`  

**Impact:** Provenance, ingestion timestamps, primary identifiers, and full-text search fields cannot be reliably discovered or queried from the published catalog schema.  
**Suggested fix:** Generate catalog schemas directly from live database metadata or add an automated CI schema-consistency check.

---

### LUMID-002 — Empty trade tape shell tables (`md.pm_us_trade_tape`, `md.kalshi_trade_tape`)

**Severity:** High  
The tables `md.pm_us_trade_tape` (0 rows) and `md.kalshi_trade_tape` (1 row) exist in the `md` schema as unpopulated skeletons, despite having names that strongly suggest active trade tape streams. The actual historical trade data is populated under `prediction_markets.polymarket_trades` (19.43M rows) and `prediction_markets.kalshi_trades`.  

**Impact:** Users and automated ETL pipelines attempting to ingest market trades from `md.*_trade_tape` conclude that trade data is missing or broken.  
**Suggested fix:** Deprecate/drop the empty shell tables, add alias views redirecting to `prediction_markets.*_trades`, or populate `md.*_trade_tape` via active pipeline replication.

---

### LUMID-003 — Polymarket condition-level candles mix YES and NO trades into unified OHLC bars

**Severity:** Critical  
The endpoint `/prediction-markets/candles/polymarket/{condition_id}` constructs OHLC bars by aggregating trades across *all* outcome token IDs associated with the condition without outcome segregation.  

**Evidence:** In binary prediction markets where YES trades at \$0.15 and NO trades at \$0.85, a single 1-minute candle reports Open=\$0.15, High=\$0.85, Low=\$0.15, Close=\$0.85.  
**Impact:** Intraday condition-level candles exhibit artificial 70-point volatility swings and are invalid for directional probability or belief-state time series analysis.  
**Suggested fix:** Either:
1. Provide a token-scoped candle endpoint `/prediction-markets/candles/polymarket/token/{asset_id}`; or
2. Segregate condition candles into separate YES/NO price channels.

---

### LUMID-004 — REST API `/prediction-markets/orderbook/polymarket/{asset_id}` historical snapshot unreachability

**Severity:** High  
While the backend table `prediction_markets.polymarket_orderbook_snapshots` contains **105M rows** (spanning 2025-10-14 to 2026-08-30), the REST endpoint `/prediction-markets/orderbook/polymarket/{asset_id}` with `from`/`to` parameters returned **0 rows** when querying historical active asset IDs during May 2026.  

**Impact:** REST consumers cannot retrieve historical L2 orderbook depth despite data existing in the underlying warehouse.  
**Suggested fix:** Verify index coverage on `(asset_id, snapshot_ts)` in the REST backend query layer and ensure the REST router maps historical queries to `polymarket_orderbook_snapshots`.

---

### LUMID-005 — Parameter name mismatch on search endpoints (`q` vs `query`)

**Severity:** Medium  
The search endpoints `/prediction-markets/markets/search` and `/kols/tweets/search` strictly require the parameter `q`. Passing `query` (the standard in general REST APIs and FMP endpoints) does not return a descriptive parameter validation error (HTTP 400/422), but silently returns empty/unfiltered results.  

**Impact:** Integrations following standard REST conventions silently fail to filter records.  
**Suggested fix:** Accept both `q` and `query` as aliases, or return an explicit HTTP 422 Unprocessable Entity when an unrecognized query parameter is supplied.

---

### LUMID-006 — Complete absence of Equity tick trades and L2 depth tables despite 6.2B-row 1-min OHLCV

**Severity:** Medium  
While traditional equity data includes massive intraday OHLCV (`market.ohlc_1min` with 6.24B rows covering 1990–2026 across 5,362 symbols via FMP), there are **zero equity tick/trade tape tables** and **zero equity L2 order book/depth tables** in the entire database catalog (searches for `trade`, `order_book`, `l2`, `depth`, `nbbo` match only prediction markets).  

**Impact:** Equity quantitative research cannot conduct microstructure, order arrival, or tick-level execution analysis.  
**Suggested fix:** Explicitly document in catalog guides that tick trades and L2 depth are supported exclusively for prediction markets (Polymarket / Kalshi), not equities.

---

### LUMID-007 — Integer-second timestamp truncation in historical REST feeds

**Severity:** Medium  
Source timestamps in tweet archives (`/kols/{handle}/tweets/history`) and trade logs (`/prediction-markets/trades/polymarket/{condition_id}`) are formatted in ISO 8601 UTC with **zero fractional digits** (e.g. `2026-05-20T16:00:00Z`).  

**Impact:** Millisecond / sub-second event ordering and high-frequency latency attribution are unidentifiable from historical REST archives without prospective synchronized SSE receipt logging.  
**Suggested fix:** Preserve microsecond/millisecond precision (`YYYY-MM-DDTHH:MM:SS.sssZ`) where available from upstream exchange websockets and X/Twitter snowflake IDs.

---

### LUMID-008 — Schema variation in Polymarket market detail outcome-to-token mappings

**Severity:** Medium  
The endpoint `/prediction-markets/markets/polymarket/{condition_id}` returns outcome mappings inconsistently:
- Some market categories return parallel arrays: `outcomes: ["Yes", "No"]` and `clob_token_ids: ["115462...", "607436..."]`.
- Other endpoints / markets return object arrays: `outcomes: [{"name": "YES", "token_id": "..."}, ...]`.

**Impact:** Client parsers assuming a uniform object structure fail or risk index-inversion between YES and NO tokens.  
**Suggested fix:** Standardize all market endpoints on a single canonical outcome object list schema: `outcomes: [{"name": "YES", "token_id": "...", "price": ...}, ...]`.
