"""Scoring for the eval: pure functions, no network, no model. Tested in tests/test_eval.py.
(agent.checks is imported for the judge's answer names only.)

A row compares Nordavo's label with the agent's decision on four fields: language, category,
priority, action. The labels come from GET /examples only; no model writes them.
"""
from agent.checks import VERDICT_CHECKS

FIELDS = ("language", "category", "priority", "action")


def judge_names(checks):
    """The judge's failed answers, as names only (its notes can quote the draft). Four states:
    None (the judge was never reached: no draft, or a code check stopped it), [] (judged, passed),
    the names (judged, failed), ["check_call_failed"] (the back-translation or judge call itself failed)."""
    if checks is None or "model" not in checks:
        return None
    names = [p for p in checks["model"] if p in VERDICT_CHECKS]
    return ["check_call_failed"] if checks["model"] and not names else names


def score_row(example_id, label, decision, extra=None, error=None):
    """One example. decision is the dict decide_ticket() returns, or None if the model failed.
    Holds ids, labels, predicted fields and counts only: never ticket text, drafts or reasons."""
    label = {f: label[f] for f in FIELDS}
    predicted = {f: decision[f] for f in FIELDS} if decision else None
    passed = {f: bool(predicted) and predicted[f] == label[f] for f in FIELDS}
    passed["all"] = all(passed[f] for f in FIELDS)
    calls = (extra or {}).get("model_calls", [])
    checks = (extra or {}).get("checks")
    return {
        "id": example_id, "label": label, "predicted": predicted, "pass": passed,
        "route_reason": decision.get("route_reason") if decision else None,
        "rule_flags": decision.get("flags", []) if decision else [],
        "checks": None if checks is None else sorted(k for k, v in checks.items() if v),  # names only
        "judge_failed": judge_names(checks),
        "error": error,
        "tokens_in": sum(c["in"] for c in calls), "tokens_out": sum(c["out"] for c in calls),
        "cost_usd": round(sum(c["cost_usd"] for c in calls), 6),
    }


def action_miss(row):
    """How the action is wrong, worst first: "unsafe" (any wrong close, since no human sees a closed
    ticket again, or a reply where a human was needed), "lost_work" (handed to a human where the label
    replies or closes), "other" (a reply where the label closes), or None if right."""
    want = row["label"]["action"]
    got = (row["predicted"] or {}).get("action")
    if got == want:
        return None
    if got == "close" or (want == "handoff" and got == "reply"):
        return "unsafe"
    if got in ("handoff", None):     # a model failure leaves the ticket to a human
        return "lost_work"
    return "other"


def totals(rows):
    """Per-field correct counts, action misses by kind, replies made versus labelled, tokens and cost."""
    n = len(rows)
    out = {"n": n, **{f: sum(r["pass"][f] for r in rows) for f in FIELDS}, "all": sum(r["pass"]["all"] for r in rows)}
    misses = [action_miss(r) for r in rows]
    out.update({
        "unsafe": misses.count("unsafe"), "lost_work": misses.count("lost_work"), "other_miss": misses.count("other"),
        "replies_labelled": sum(r["label"]["action"] == "reply" for r in rows),
        "replies_made": sum((r["predicted"] or {}).get("action") == "reply" for r in rows),
        "replies_right": sum(r["label"]["action"] == "reply" and r["pass"]["action"] for r in rows),
        "model_errors": sum(r["error"] is not None for r in rows),
        # how often each judge answer said no, out of the drafts that reached the judge
        "reached_judge": sum(r.get("judge_failed") not in (None, ["check_call_failed"]) for r in rows),
        "judge_failed": {name: sum(name in (r.get("judge_failed") or []) for r in rows)
                         for name in VERDICT_CHECKS + ("check_call_failed",)
                         if any(name in (r.get("judge_failed") or []) for r in rows)},
        "tokens_in": sum(r["tokens_in"] for r in rows), "tokens_out": sum(r["tokens_out"] for r in rows),
        "cost_usd": round(sum(r["cost_usd"] for r in rows), 6),
    })
    out["cost_per_100_usd"] = round(out["cost_usd"] / n * 100, 4) if n else 0.0
    return out


RANGE_KEYS = FIELDS + ("all", "unsafe", "lost_work", "replies_made", "replies_right", "model_errors", "cost_per_100_usd")


def across_runs(results):
    """Several results files of the same eval: the range (min, max) of each total, and the example ids
    whose outcome changed between runs (the judge is noisy, so one run is not a number)."""
    ranges = {k: (min(r["totals"][k] for r in results), max(r["totals"][k] for r in results)) for k in RANGE_KEYS}
    outcomes = {}
    for r in results:
        for row in r["rows"]:
            outcomes.setdefault(row["id"], set()).add(
                (tuple((row["predicted"] or {}).get(f) for f in FIELDS), row["route_reason"]))
    flipped = sorted(i for i, seen in outcomes.items() if len(seen) > 1)
    return {"runs": len(results), "ranges": ranges, "flipped": flipped}


def fmt_range(lo, hi):
    return f"{lo}" if lo == hi else f"{lo}-{hi}"
