"""Reproduce the two frozen question/context calls; no outcome scoring."""
import argparse
from trial_common import chat, show

BASE = 'As of 2026-09-14, estimate these unresolved markets without browsing. Prices and outcomes are withheld. Do not invent current evidence. Return only JSON {"forecasts":[{"id":"1115677","p_yes":0.5,"evidence_sufficient":false},{"id":"1129896","p_yes":0.5,"evidence_sufficient":false}]}. Questions: 1115677: Jerome Powell out from Fed Board by December 31, 2026? 1129896: Will KPRF win the most seats in the next Russian parliamentary election (listed end 2026-09-30)?'
EXTRA = ' Additional resolution criteria, not news: Powell must leave the Board of Governors; only leaving the Chair position does not qualify. KPRF outcome uses greatest State Duma seat count, ties by votes then alphabetical abbreviation; unresolved by 2027-09-30 resolves Other.'

def valid(answer):
    try:
        rows = answer["forecasts"]
        return (len(rows) == 2 and {r["id"] for r in rows} == {"1115677", "1129896"}
                and all(type(r["p_yes"]) in (int, float) and 0 <= r["p_yes"] <= 1
                        and isinstance(r["evidence_sufficient"], bool) for r in rows))
    except (TypeError, KeyError):
        return False

def run(call=chat, model="qwen3.8-27b"):
    attempts = []
    for name, prompt in [("question_only", BASE), ("with_criteria", BASE + EXTRA)]:
        item = call(model, prompt, max_tokens=800, thinking=False)
        item.update(condition=name, valid=valid(item.get("answer")))
        attempts.append(item)
    return {"trial": "TimeSeek-inspired frozen-input demonstration", "markets": 2,
            "valid_calls": sum(a["valid"] for a in attempts), "attempts": attempts,
            "limitation": "No archived search, settlement labels, Brier score or PnL; later model knowledge may leak."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3.8-27b")
    args = parser.parse_args()
    show(run(model=args.model))
