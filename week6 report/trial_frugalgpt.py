"""Four synthetic cases: always-first, always-second and actual escalation."""
import argparse
import json
from trial_common import chat, show

RULE = "YES iff the Fed cuts its target rate by at least 25 basis points at the September meeting."
POSTS = ["The official September decision cuts the target rate by 50 basis points.",
         "The official September decision keeps the target rate unchanged.",
         "NASA successfully launched a lunar probe today.",
         "Analysts expect a rate cut; the September meeting has not happened and no decision has been announced."]
CASES = [{"id": i, "market": RULE, "post": post} for i, post in zip("ABCD", POSTS)]
GOLD = dict(zip("ABCD", ["SUPPORTS_YES", "CONTRADICTS_YES", "IRRELEVANT", "INSUFFICIENT"]))
PREFIX = 'Classify these synthetic market/post pairs using only the supplied text. Labels: SUPPORTS_YES (establishes YES), CONTRADICTS_YES (establishes NO), IRRELEVANT (unrelated), INSUFFICIENT (related but does not establish either outcome). Return only JSON {"items":[{"id":"A","label":"...","confidence":0.99}]}. Cases: '

def rows(result, expected):
    try:
        items = result["answer"]["items"]
        if len(items) != len(expected) or {r["id"] for r in items} != set(expected):
            return {}
        if not all(r["label"] in GOLD.values() and type(r["confidence"]) in (float, int)
                   and 0 <= r["confidence"] <= 1 for r in items):
            return {}
        return {r["id"]: r for r in items}
    except (KeyError, TypeError):
        return {}

def metric(predictions, calls):
    tokens = [c.get("total_tokens") for c in calls]
    return {"correct": sum(predictions.get(i, {}).get("label") == label for i, label in GOLD.items()),
            "N": 4, "valid_answers": len(predictions),
            "seconds": round(sum(c["seconds"] for c in calls), 3),
            "total_tokens": sum(tokens) if all(isinstance(n, int) for n in tokens) else None}

def run(call=chat, first="qwen3.8-27b", second="deepseek-v4-flash", threshold=.98):
    if not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between zero and one")
    cheap = call(first, PREFIX + json.dumps(CASES))
    strong = call(second, PREFIX + json.dumps(CASES))
    a, b = rows(cheap, GOLD), rows(strong, GOLD)
    subset = [c for c in CASES if a.get(c["id"], {}).get("confidence", -1) < threshold]
    cascade = dict(a)
    calls = [cheap]
    if subset:
        escalated = call(second, PREFIX + json.dumps(subset))
        ids = [c["id"] for c in subset]
        # Failed escalation is unknown, not a silently accepted earlier answer.
        for i in ids:
            cascade.pop(i, None)
        cascade.update(rows(escalated, ids))
        calls.append(escalated)
    return {"trial": "FrugalGPT-inspired synthetic demonstration", "threshold": threshold,
            "escalated_ids": [c["id"] for c in subset], "always_first": metric(a, [cheap]),
            "always_second": metric(b, [strong]), "cascade": metric(cascade, calls),
            "attempts": [cheap, strong] + calls[1:],
            "limitation": "Uncalibrated confidence; four synthetic cases; tokens are not currency cost."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first", default="qwen3.8-27b")
    parser.add_argument("--second", default="deepseek-v4-flash")
    parser.add_argument("--threshold", type=float, default=.98)
    args = parser.parse_args()
    show(run(first=args.first, second=args.second, threshold=args.threshold))
