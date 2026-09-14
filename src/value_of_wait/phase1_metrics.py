"""Evaluator-only metrics; never imported by a model input adapter."""
from .phase1_replay import replay_actions


def counterfactual_pair(fast, deep, books, settings):
    if fast["event_id"] != deep["event_id"] or fast["decision_ts"] != deep["decision_ts"] or fast["exit_due_ts"] != deep["exit_due_ts"] or deep["available_ts"] < fast["available_ts"]:
        raise ValueError("Counterfactual actions need a shared episode and ordered completion")

    def utility(action, available):
        if action["direction"] == "NONE":
            return 0.0, None
        result = replay_actions([dict(action, available_ts=available, compute_cost=0)], books, settings)
        if result["metrics"]["closed_positions"] != 1:
            return None, None
        return result["metrics"]["net_realized_pnl"], result["fills"][0]["ts"]

    f, f_entry = utility(fast, fast["available_ts"])
    d_early, early_entry = utility(deep, fast["available_ts"])
    d_late, late_entry = utility(deep, deep["available_ts"])
    result = {"event_id": fast["event_id"], "fast_utility": f, "deep_at_fast_utility": d_early, "deep_utility": d_late,
              "same_deep_entry_snapshot": early_entry == late_entry if early_entry is not None and late_entry is not None else None,
              "incremental_compute_cost": deep.get("compute_cost", 0) - fast.get("compute_cost", 0),
              "complete": all(x is not None for x in (f, d_early, d_late)), "G": None, "W": None, "VOW": None,
              "VOW_after_incremental_compute": None, "interpretation": "isolated paired counterfactual; not a deployable early deep action"}
    if result["complete"]:
        result.update(G=d_early - f, W=d_late - d_early, VOW=d_late - f,
                      VOW_after_incremental_compute=d_late - f - result["incremental_compute_cost"])
    return result
