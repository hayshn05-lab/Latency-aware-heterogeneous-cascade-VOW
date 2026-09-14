# Background study: six related papers

Reading date: 14 September 2026. These papers cover forecasting, execution-aware evaluation and selective model use. Paper results below are distinct from our platform demonstrations.

## 1. TimeSeek

[Paper, v1](https://arxiv.org/html/2604.04220v1)

- **Scenario / method:** Prediction-market forecasting at different lifecycle stages; compare LLM forecasts with and without date-filtered search.
- **Data / evaluation:** 150 binary Kalshi markets, five checkpoints and ten models. Brier score and Brier skill score compare forecasts with contemporaneous market probabilities; market prices are withheld from model inputs.
- **Pros:** Makes the value and timing of extra information directly testable.
- **Cons:** Limited market sample; retrospective search filtering does not itself guarantee historically archived content. Forecast skill does not establish executable profit after latency.
- **Our application:** Use a shared question-only control and an additional-evidence condition. Our small trial adds resolution rules only, so it tests an interface mechanism rather than reproducing search-based forecasting.

## 2. PolyBench

[Paper, v1](https://arxiv.org/html/2604.14199v1)

- **Scenario / method:** Compare LLM prediction-market agents using synchronized information and order-book depth; confidence controls participation and allocation.
- **Data / evaluation:** 38,666 market snapshots across 4,997 events during 6–12 February 2026; seven LLMs. Reports directional accuracy and return/risk measures, including confidence-weighted returns, APY and Sharpe; compares models and weighting choices.
- **Pros:** Connects model predictions to depth and portfolio allocation.
- **Cons:** Short observation period, participation selection and hold-to-settlement assumptions limit transfer to intraday exits. Confidence weighting is not evidence of calibration.
- **Our application:** Borrow explicit allocation/depth accounting, while retaining rejected actions in denominators and reporting exposure duration.

## 3. PredictionMarketBench

[Paper, v1](https://arxiv.org/html/2602.00133v1)

- **Scenario / method:** Deterministic Kalshi event replay with agent tools, order lifecycle and fees.
- **Data / evaluation:** Four January 2026 episodes spanning crypto, weather and sports. Baselines include RandomAgent, GPT-4.1-nano and Bollinger Bands (20-period, two-standard-deviation bands). Metrics include PnL, return, drawdown, traded contracts and fill rate.
- **Pros:** Provides explicit trading mechanics and reproducible agent comparisons.
- **Cons:** Four episodes provide limited breadth; simulated fills and agent scheduling do not establish realistic queue position or latency effects.
- **Our application:** Reuse accounting and baseline discipline. Lumid's similarly named trading facilities must be checked independently; the paper does not validate our platform's replay semantics.

## 4. FrugalGPT

[Paper, v1](https://arxiv.org/html/2305.05176v1)

- **Scenario / method:** A learned answer-quality scorer and thresholds cascade among LLM APIs under a budget.
- **Data / evaluation:** HEADLINES (finance, 10,000 examples), OVERRULING (law, 2,400), and CoQA (reading, 7,982). Evaluates answer accuracy versus API cost against individual LLMs, including GPT-4.
- **Pros:** Directly operationalizes selective escalation and cost–quality trade-offs.
- **Cons:** Requires labeled training/calibration data; API prices and model quality can change. Accuracy optimization omits execution delay and financial utility.
- **Our application:** First verify sequential escalation with a fixed confidence threshold; later replace self-reported confidence with a calibrated score trained only on permitted splits.

## 5. RouteLLM

[Paper, v4](https://arxiv.org/html/2406.18665v4)

- **Scenario / method:** Route queries between stronger and weaker models using preference-trained scoring, including ranking, matrix-factorization and classifier approaches.
- **Data / evaluation:** Chatbot Arena preferences and augmented supervision; MT-Bench, MMLU and GSM8K evaluation. Compares routing with random selection and strong/weak endpoints, reporting quality retention, strong-model use and cost measures.
- **Pros:** Tests whether learned routing generalizes beyond its training distribution.
- **Cons:** General benchmark preferences may not transfer to market relevance or signal direction; model-call savings omit trading-window loss.
- **Our application:** A later learned router can select additional reasoning, but requires domain labels and available-at-decision-time features.

## 6. OpenMarket

[Paper, v1](https://arxiv.org/abs/2607.26245)

- **Scenario / method:** Analyze paired Polymarket BTC 15-minute markets and Binance observations, including cross-venue timing and walk-forward prediction.
- **Data / evaluation:** The described corpus contains over 727 million rows; a 43-feature logistic model is compared with the market's own book-implied probability. Evaluates forecasting and normalized simulated payoff.
- **Pros:** Treats the market probability as a serious baseline and documents a negative out-of-sample finding rather than assuming external information creates alpha.
- **Cons:** Crypto-specific, high-frequency data and clock-alignment assumptions differ sharply from our sparse weekly snapshots.
- **Our application:** Require improvement over market information before interpreting semantic accuracy as trading value. Do not transfer high-frequency conclusions to five-minute polling.

## Design implications

TimeSeek motivates the information comparison; FrugalGPT and RouteLLM motivate selective computation; PolyBench and PredictionMarketBench motivate execution accounting; OpenMarket motivates a demanding market baseline. Our first feasible study should separate **semantic utility, measured decision latency, and conditional execution outcomes**. None of these papers establishes a profitable window for our dataset.
