# Reproduce the Week 6 platform demonstrations

Python 3.11+, standard library only. Run from the repository root:

```powershell
python "week6 report/trial_timeseek.py"
python "week6 report/trial_frugalgpt.py"
```

Set `LUMID_PAT` in your environment or the ignored repository `.env`. No credentials are embedded in these scripts. Each command makes live, potentially billable model calls and prints JSON to the terminal; it writes no files and performs no trading. `--help` makes no network calls.

The first script reproduces the **successful revised pair** of forecast requests with the two frozen questions and criteria from the September 14 report. It deliberately does not repeat live SQL discovery, which can return different markets later, or the initial exhausted-token requests. The report retains the original acquisition SQL. This is a model-call reproduction, not an acquisition pipeline or point-in-time backtest; newer models can know subsequent outcomes.

The second script runs the four synthetic cases with always-Qwen, always-DeepSeek and a real confidence-gated escalation. Gold labels stay outside prompts. Default threshold 0.98 is fixed before requests. Missing/malformed answers stay in the denominator; failed escalations remain unknown. The shared Qwen stage is counted once per policy, not billed twice in the request log.

Model aliases and latency can change; exact old numbers are not expected. Results include request times, hashes, usage, failures and structured answers. Credentials and raw error bodies are suppressed; redirects are disabled. `trial_common.py` is the shared HTTP helper.

Offline behavioral verification (mocked API, no spend):

```powershell
python -B -m unittest discover -s tests -p test_week6_trials.py -v
```

The original three Markdown reports are presentation documents. Generated data/results, local source documents and legacy entrypoints are excluded from Git; see the repository `.gitignore`.
