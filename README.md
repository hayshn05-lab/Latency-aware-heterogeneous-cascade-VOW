# Value of Waiting in Prediction Markets

Research infrastructure for the question: **when is deeper semantic reasoning worth its latency?**

Start with [current status](CURRENT_STATUS.md), the [research plan](docs/research_plan_current.md), and [workspace map](docs/workspace_map.md). The weekly warehouse dataset is acquired. The [phase-one snapshot experiment design](docs/specs/phase1_experiment.md) is ready; execution is deferred by the user and the interface implementation remains a draft. The [September 13 readiness report](reports/weekly_replay_readiness.md) is preserved historical evidence. No strategy profitability is claimed.

## Completed phase-one cleaning (reproduction only)

```powershell
python scripts/build_phase1.py --config config/phase1_v1.json --offline
```

Versioned p1 tables preserve raw records and separate conditional snapshot simulation from strict historical eligibility. See [pipeline contract](docs/specs/phase1_pipeline.md).

## Weekly dataset

The configured initial window is **2026-09-06 through 2026-09-12 UTC**, with end-exclusive 2026-09-13. Tweets, Polymarket trades and L2 rows use that event-time window. Market metadata uses scheduled overlap and is explicitly retrospective, not a proven historical candidate universe.

```powershell
# Online: reads LUMID_PAT from environment or the ignored local .env.
python scripts/run_weekly.py --config config/weekly_v1.json

# Offline: no credential or network required; rebuilds from query materializations.
python scripts/run_weekly.py --config config/weekly_v1.json --offline

# Structural replay-readiness audit, with no models or trading.
python scripts/audit_weekly.py --config config/weekly_v1.json
```

Raw SQL responses: `data/raw/findata/weekly_v1/`. SQLite database: `data/interim/weekly_v1/research.sqlite`. Query/completeness manifest and audit aggregates: `data/releases/weekly_v1/`. A fresh clone requires the ignored raw cache to reproduce source-derived results.

SQLite preserves row versions and source provenance and supports incremental imports. See [database contract](docs/specs/research_database.md). Core code uses Python 3.11+ standard library only.

## Verification

```powershell
python -m compileall -q src scripts tests
python -m unittest discover -s tests -v
```

## Preserved pilot and earlier audits

The small tweet-count insight experiment remains in `outputs/pilot/`, with `config/pilot.json`, the original ignored raw cache, and [pilot report](reports/pilot_summary.md). It measures non-executable price-state proxies, not a proven profit window.

```powershell
python scripts/run_pilot.py run --config config/pilot.json --output outputs/pilot --offline
python scripts/run_pilot.py audit --config config/pilot.json --output outputs/pilot --offline
```

Earlier REST entrypoints are under `scripts/legacy/`; their config/raw paths remain unchanged. [Legacy reproduction](docs/archive/replay_audit_reproduction.md) describes the retained replay audit. Superseded plans are in `docs/archive/`. Platform references are in `docs/reference/lumid/`; original T2 files are under ignored `data/raw/eventxbench/local_t2/`.

## Week 6 platform reproductions

See [run instructions](<week6 report/README.md>) for two small, live model API demonstrations. These do not launch the deferred full phase-one study.

Data, generated outputs/reports, local platform reference copies and legacy entrypoints remain local and are excluded from Git. Links into those directories describe local artifacts and will not resolve in a fresh clone until the corresponding artifacts are supplied or regenerated. Maintained presentation reports are under `week6 report/`.

Previously published artifacts remain in Git history and the remote tree; this update leaves their tracked contents unchanged. Ignore rules prevent new untracked artifacts from being added.
