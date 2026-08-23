# Findata Tweet-to-Market Latency Pilot: Protocol

Status: approved narrow pilot protocol  
Protocol date: 2026-08-23  
Raw-data boundary: Findata only  
Alignment-method reference: EventXBench only

## 1. Decision this pilot informs

The pilot estimates whether a slow reasoning stage that takes seconds or minutes can still observe a meaningful portion of a tweet-linked prediction-market repricing. It is a calibration study for cascade latency budgets, not a causal study of tweets and not an execution backtest.

The operational question is:

> After a mechanically aligned tweet or short tweet bundle is complete, how quickly does the linked market produce a new trade, and how much of the subsequent 30-minute price move remains observable after delays of 5 seconds to 10 minutes?

## 2. Data scope

The default pilot uses one completed, mechanically aligned event family:

- source handle: `elonmusk`;
- tweet window: `2026-05-19T16:00:00Z` through `2026-05-26T16:00:00Z`;
- linked markets: Polymarket contracts whose question refers to the number of Elon Musk posts in that same window;
- source observations: Findata historical tweets, Polymarket market metadata, and token-level trades.

This family is selected because every source post changes the running count used by every linked contract. That removes semantic candidate-generation ambiguity from this calibration run. It does not demonstrate general event-market alignment or semantic reasoning quality.

The EventXBench repository is a methodological reference for frozen candidate sets, explicit `NONE`, temporal splitting, leakage control, and human adjudication. Gated EventXBench records are not silently substituted into the pilot.

## 3. Non-negotiable data rules

1. The Lumid personal access token is read only from the `LUMID_PAT` environment variable. It must never appear in a command-line flag, log, cache key, report, source file, or committed artifact.
2. Polymarket trades are canonicalized to the probability of `YES`: a YES-token price remains `p`; a NO-token price becomes `1 - p`.
3. Findata condition-level OHLCV is not used. It may mix YES and NO token prints in one candle and is therefore not a directional probability series.
4. A market is included only when its metadata provides an unambiguous YES/NO outcome-to-token mapping.
5. Raw responses are cached locally under ignored paths. A committed manifest records endpoint, request parameters with secrets removed, retrieval time, row count, and SHA-256 digest.
6. Historical order-book data are audited separately. Unless aligned L2 snapshots pass coverage and timestamp checks, all economic results are labelled `non-executable price-move proxy`; they are not called profit, return, or realizable PnL.
7. Timestamp precision is measured from the returned records. Millisecond claims are forbidden when either tweet or trade timestamps have only second precision.

## 4. Event construction

Tweets separated by no more than 60 seconds are grouped into one bundle.

- `bundle_start`: timestamp of the first tweet;
- `decision_time`: timestamp of the final tweet in the bundle;
- baseline target: one second before `bundle_start`;
- delay targets after `decision_time`: 5, 10, 30, 60, 120, 300, 600, and 1,800 seconds.

For a delay `h`, the bundle is marked clean when no later tweet occurs in `(decision_time, decision_time + h]`. Clean and contaminated counts are both reported. The default headline table uses clean observations. This is a descriptive isolation rule, not proof of causality.

## 5. Price observations and missingness

For each bundle-market-target tuple, the observed state is the most recent canonicalized trade at or before the target. Its age is retained. The default maximum acceptable age is 900 seconds.

An event-market tuple is eligible for a delay only when both its baseline and delayed observations satisfy the age limit. Forward-filled prices without a new post-event trade remain valid state observations but are flagged `updated = false`.

The pipeline reports, for every delay:

- eligible bundle-market pairs;
- clean eligible pairs;
- fraction with at least one new trade since `decision_time`;
- median and interquartile range of absolute repricing in probability points;
- median and interquartile range of the remaining-move proxy;
- timestamp staleness summaries.

Missing values are never converted to zero.

## 6. Metrics

### 6.1 First-print latency

For each bundle, find the earliest linked-market trade strictly after `decision_time` and report the distribution of elapsed seconds. This measures the resolution of the historical trade feed, not exchange matching-engine latency.

### 6.2 Observed repricing

For market `m`, baseline price `p_m(0)`, and delayed state `p_m(h)`:

`absolute_repricing_m(h) = |p_m(h) - p_m(0)|`.

The primary unit in tables is probability points, `100 * absolute_repricing_m(h)`.

### 6.3 Remaining-move proxy

Let the descriptive endpoint be 1,800 seconds after `decision_time`:

`remaining_m(h) = |p_m(1800) - p_m(h)| / |p_m(1800) - p_m(0)|`.

The denominator must be at least 0.005 probability (0.5 probability points). Values are not clipped: values above 1 reveal reversals or overshoot and negative values are impossible under this absolute-distance definition. This is an upper-bound mark-to-later-price proxy. It ignores spread, fees, queue position, size, and impact.

The 1,800-second endpoint is a measurement horizon, not an acceptable model latency.

## 7. Interpretation gates

The report must distinguish three conclusions:

- **identifiable:** record precision and update density support the requested delay;
- **descriptively estimable:** price-state changes can be summarized, but execution is not known;
- **execution-estimable:** aligned bid/ask depth exists and a fill model is specified.

This pilot is expected to reach at most the second level. Cascade design may use its first-print and remaining-move results as timing evidence, but main-paper PnL requires a later execution dataset or a prospective recorder.

## 8. Acceptance criteria

The pilot is complete when:

- all source and canonicalization tests pass;
- the live run creates a redacted provenance manifest;
- at least one linked market and one tweet bundle survive validation;
- delay results include explicit `n`, coverage, and staleness;
- the report states whether seconds, minutes, and milliseconds are identifiable;
- every chart defines its unit, aggregation, uncertainty summary, and missingness;
- rerunning against cached raw files reproduces the committed aggregate outputs without a token.

