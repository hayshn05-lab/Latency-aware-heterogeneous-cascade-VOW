# Implementation Plan: Findata Tweet-to-Market Latency Pilot

Spec: `docs/specs/pilot_protocol.md`

## Global constraints

- Implement only the prior data audit and latency pilot. The full semantic cascade remains a reviewed plan, not implemented code.
- Findata is the sole raw-data provider for the pilot; EventXBench supplies alignment and evaluation design concepts only.
- Never persist or print credentials.
- Use Python 3.11+ standard library for the core pipeline so a fresh environment can run it without package installation.
- Keep source extracts out of Git; commit only aggregate, redacted, reproducible artifacts.
- Treat seconds and minutes as the decision range. Treat 30 minutes only as an outcome endpoint. Do not imply that an LLM may take hours.
- Do not infer executable profit from last trades or mixed-outcome candles.
- Write a failing test before each behavior and run the focused test before implementation.

## Task 1: Executable pilot core

Create the Python package, configuration, and tests for:

- authenticated, retrying Findata JSON reads with secret-safe request records;
- tolerant parsing of market, tweet, and trade response envelopes;
- unambiguous YES/NO token mapping;
- YES-probability trade canonicalization;
- tweet bundling and clean-horizon flags;
- last-trade state lookup with staleness;
- first-print, repricing, remaining-move, and coverage summaries;
- deterministic CSV, JSON, Markdown, and SVG output writers;
- online acquisition and offline-cache execution modes.

The test suite must use fixtures only and must not require a token or network.

### Task 1 exact interface

Read `docs/specs/pilot_protocol.md` completely before coding. Create:

- `pyproject.toml`: Python `>=3.11`, no runtime dependencies, package under `src/`;
- `config/pilot.json`: source handle, UTC window, search query, exact title-window match fields, bundle gap `60`, horizons `[5, 10, 30, 60, 120, 300, 600, 1800]`, staleness `900`, and terminal-move floor `0.005`;
- `src/value_of_wait/client.py`: Findata client, retry policy, redacted request ledger, content-addressed JSON cache;
- `src/value_of_wait/parsing.py`: tolerant response-envelope parsing and typed normalized records;
- `src/value_of_wait/study.py`: pure event construction and metric functions;
- `src/value_of_wait/outputs.py`: stable CSV/JSON/Markdown/SVG writers;
- `src/value_of_wait/pipeline.py`: acquisition, validation, analysis, and artifact orchestration;
- `src/value_of_wait/cli.py` and `scripts/run_pilot.py`;
- credential-free fixtures and `unittest` tests;
- placeholder `data` and `outputs` directories retained with `.gitkeep` where needed.

The exact commands are:

```text
python scripts/run_pilot.py audit --config config/pilot.json --output outputs/pilot
python scripts/run_pilot.py run --config config/pilot.json --output outputs/pilot
python scripts/run_pilot.py run --config config/pilot.json --output outputs/pilot --offline
```

Online commands read only `LUMID_PAT`. If absent, exit `2` with a secret-free instruction. Offline mode must not read or require that variable. Default base URL is `https://lum.id/findata`; every endpoint remains configurable for fixture tests. Search paginates and each market receives an inclusion or exclusion reason.

Deterministic aggregate artifacts are `data_manifest.json`, `market_validation.csv`, `event_bundles.csv`, `delay_profile.csv`, `first_print_latency.csv`, `observations.csv`, `summary.json`, `latency_profile.svg`, and `generated_findings.md` under the selected output directory. SVG uses common positional scales, reports sample size and coverage, does not smooth, and exposes missingness.

Use `unittest`. Record focused red-to-green evidence and run the full suite plus `python -m compileall -q src scripts tests`. Commit the task and write its full report to the SDD task report path supplied by the controller.

## Task 2: Live pilot execution

Run the pipeline with the user-provided credential supplied through a non-echoing transient environment. Inspect response shapes and make the smallest parser corrections needed. Record:

- endpoint availability and returned coverage;
- included and excluded markets with reasons;
- tweet and bundle counts;
- source timestamp precision;
- trade coverage and first-print latency;
- delay-profile metrics and their sample sizes;
- L2 availability audit for the same market family.

Rerun in offline mode and compare aggregate digests. No raw source record is committed.

## Task 3: Judgment package

Create:

- `README.md` with exact online, offline, and test commands;
- `AGENTS.md` with human/agent research invariants;
- `reports/pilot_summary.md` with the actual findings and limitations;
- `docs/data_audit.md` with the source capability verdict;
- `docs/research_plan.md` defining the proposed full study, hypotheses, measures, baselines, cascade variants, model-latency protocol, leakage controls, robustness checks, stage gates, and implementation tasks;
- an explicit list of decisions requiring supervisor approval before the main research is implemented.

## Verification

Run, in order:

1. `python -m unittest discover -s tests -v`
2. online pilot run with `LUMID_PAT` set transiently
3. offline replay from the saved local cache
4. aggregate digest comparison
5. `python -m compileall -q src scripts tests`
6. secret scan over tracked and untracked workspace files, excluding `.git` and ignored raw caches
7. independent specification and code review
