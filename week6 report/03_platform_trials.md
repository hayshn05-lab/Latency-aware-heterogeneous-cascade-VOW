# Two small related-work trials on Lumid

Executed on 14 September 2026 under the user's new request. **Both model-side adaptations ran successfully; neither is a full paper reproduction or an executable-profit experiment.** Requests ran in memory using the existing PAT. No strategy, signal or order was published; only Markdown summaries are retained.

## Trial 1 — TimeSeek-inspired information comparison

**Original work:** TimeSeek compares forecasts with and without search, using Kalshi questions and outcome-based Brier metrics against market probabilities. See [paper](https://arxiv.org/html/2604.04220v1) and [background study](02_background_study.md).

**Our adaptation:** Retrieve two current Polymarket metadata records from Findata; compare question-only forecasts with forecasts additionally given resolution criteria. There was no news search, historical replay or settlement-label scoring.

The actual SQL, submitted to `POST https://lum.id/findata/retrieve` with JSONL output, was:

```sql
SELECT id, condition_id, question, end_date,
       raw->>'description' AS description
FROM prediction_markets.polymarket_markets
WHERE active = true AND closed = false
  AND end_date > '2026-09-14T00:00:00Z'
  AND question ILIKE '%Fed%'
ORDER BY id LIMIT 2;
```

Retrieval and reading the materialized response took 0.882 seconds. This is a tiny deterministic convenience sample, not a representative universe. `Fed` also matched `Federation`, exposing a lexical-discovery false positive.

| ID | Question / additional criteria | Question-only p(YES) | With criteria p(YES) |
|---|---|---:|---:|
| 1115677 | Jerome Powell out from the Fed Board by December 31, 2026? Leaving only the Chair role does not qualify. | 0.05 | 0.05 |
| 1129896 | Will KPRF win the most seats in the next Russian parliamentary election? Resolve by Duma seats, then votes/alphabetical tie-breaks; unresolved by September 30, 2027 resolves Other. | 0.95 | 0.05 |

The second market's listed end was September 30, 2026; its criteria included a later unresolved-outcome deadline. The additional input exposed that distinction. These probabilities are unvalidated model outputs, not accepted forecasts or recommendations.

**How the model calls were made:** `POST https://lum.id/llm/v1/chat/completions`, model `qwen3.8-27b`, temperature 0. The prompt fixed the as-of date to September 14, withheld prices/outcomes, prohibited invented evidence and requested JSON containing market ID, `p_yes` and `evidence_sufficient`. The additional-context arm appended only resolution rules.

| Request setting | Question-only | With criteria |
|---|---|---|
| Initial: 400-token completion budget | 6.027 s; 617 total tokens; no answer | 5.953 s; 728 total tokens; no answer |
| Revised: 800-token budget, `enable_thinking=false`, shortened common prompt | 2.067 s; 264 total tokens; valid JSON | 2.026 s; 323 total tokens; valid JSON |

Both initial HTTP-200 responses exhausted their 400 completion tokens on reasoning and returned null content. Both revised calls produced valid JSON and marked evidence insufficient for both markets. The retry changed multiple settings; it is not an isolated causal test of disabling reasoning.

**Result:** Two of four attempted calls returned usable answers. The final paired comparison yielded four predictions across two markets. A 0.90 probability shift for one question shows context sensitivity, not improved accuracy. Brier score, skill against market prices, calibration and PnL remain unavailable because verified labels and aligned prices were not obtained.

## Trial 2 — FrugalGPT-inspired confidence cascade

**Original work:** FrugalGPT learns quality scores and budget-aware escalation using labeled tasks, comparing accuracy and API cost against individual models. Our trial tests only the sequential-call mechanism, using an untrained threshold. See [paper](https://arxiv.org/html/2305.05176v1).

**Dataset:** Four hand-authored synthetic cases, all using the rule: “YES iff the Fed cuts its target rate by at least 25 basis points at the September meeting.” Gold labels were kept out of model inputs.

| ID | Supplied post | Gold label |
|---|---|---|
| A | The official September decision cuts the target rate by 50 basis points. | SUPPORTS_YES |
| B | The official September decision keeps the target rate unchanged. | CONTRADICTS_YES |
| C | NASA successfully launched a lunar probe today. | IRRELEVANT |
| D | Analysts expect a rate cut; the September meeting has not happened and no decision has been announced. | INSUFFICIENT |

**Procedure:** Send all cases to Qwen; request JSON labels and confidence using only supplied text. Escalate cases with confidence below **0.98**, fixed before calls, to `deepseek-v4-flash`. Independently call DeepSeek on all four cases for the always-second-model control. Both backends used temperature 0, a 600-token completion budget and `chat_template_kwargs: {"enable_thinking": false}`.

Qwen returned confidence 0.99 for A/B/C and 0.95 for D. Only D was actually sent in the escalation request; its returned label was INSUFFICIENT. No gold-based routing was used.

| Method | Correct / N | Measured request time | Total reported tokens | Cases sent to DeepSeek |
|---|---:|---:|---:|---:|
| Always Qwen | 4/4 | 2.416 s | 440 | 0/4 |
| Always DeepSeek | 4/4 | 4.154 s | 582 | 4/4 |
| Qwen → selective DeepSeek | 4/4 | 3.986 s | 694 | 1/4 |

The cascade time/tokens sum the actual Qwen call and the actual D-only escalation (1.570 seconds, 254 tokens). The Qwen stage is shared with its control, so three API requests were made, not four. Timing is for batched requests, not per-event production latency.

**Result:** Escalation works, but this fixture demonstrates no accuracy gain or token saving: the cascade uses approximately 19% more tokens than always DeepSeek. Four easy synthetic cases cannot establish a quality ranking, calibrated confidence or generalization. Tokens are not currency cost; model prices were not measured. Qwen and DeepSeek are stage roles here, not proven cheap/strong rankings.

**Compatibility finding:** DeepSeek still reported reasoning tokens (218 in the all-case call; 83 in escalation) despite the shared thinking flag, while Qwen reported zero. Provider-specific parameter behavior and mutable model aliases need explicit handling.

## Platform checks and remaining gaps

| Capability checked | Observed result | Meaning |
|---|---|---|
| Model discovery `/llm/v1/models` | HTTP 200; Qwen and DeepSeek aliases available | Inference access works. |
| Findata SQL retrieval | HTTP success; two metadata rows read | PAT-based data access works; broad acquisition was not repeated. |
| Quant OpenAPI and strategy listing | HTTP 200 | Researcher API documentation and read access work. |
| Universe `...?venue=polymarket` | HTTP 500 | Corrected request failed. The preceding request without required `venue` returned 400 and was a caller error. |
| Kalshi active instruments, limit 3 | HTTP 200; three instrument records | Discovery works on this endpoint; this does not validate a historical tape. |
| Results listing, limit 3 | Client timeout after 25 seconds | Read attempt inconclusive; not a backtest-job failure. |
| Standalone backtest submission | No confirmed route in inspected researcher docs/OpenAPI/MCP tool listing | Not executed. This does not prove the platform lacks the capability elsewhere. |

We explored a PredictionMarketBench-style native replay before selecting FrugalGPT as the second executable trial. The documented strategy POST deploys a strategy; it was not used to substitute a recurring deployment for a one-off test.

The saved [first-run guide](../docs/reference/lumid/first-run.md) describes tape-backed and synthetic fallback behavior. Those are documented modes, **not verified results from this task**. A future trading trial must confirm the actual tape source, time range, fees, fill assumptions and absence of silent synthetic substitution.

What is still missing for the research study:

- A confirmed one-shot replay workflow with reproducible historical data and explicit execution semantics.
- Point-in-time candidate discovery, archived evidence and verified outcome/semantic labels; preset benchmark candidates are insufficient.
- A calibrated routing score, held-out family splits and realistic event batches.
- Stable model/version identifiers, consistent inference controls, currency pricing and repeated latency measurements.
- An integrated ledger linking signal availability, failed/censored actions, capital use and final trading metrics.

These trials establish a usable data-to-inference path and a working cascade mechanism. The next research milestone is a labeled, reproducible evaluation, not a claim of alpha.
