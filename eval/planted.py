"""Planted-error rig: python -m eval.planted [--runs 3] [--code-only]

Can the two check calls catch a Dutch reply that says something different from its English version? A reader
without Dutch sees only the English, so this is the error they could not catch themselves.

eval/planted_variants.json holds four honest Dutch drafts from the eval (each passed the judge) and, per draft,
four versions with one edit in the Dutch only: a negation, a wrong fact, a wrong time, a wrong actor or place.
The drafter's honest English is kept for every version. Each version, and the unchanged draft as a control, goes
through the agent's own checks: the code checks first (free), then the back-translation and the judge.

Per version and run it records: the code checks that stopped it, whether the back-translation shows the planted
meaning (an English pattern written before any run), and the judge's failed answers. "Caught" means held back by
any check; a planted version that passes everything would have reached the customer. Controls give the false-alarm
count from the same runs, and show whether a pattern also fires on an honest back-translation.

--code-only runs the code checks alone (no model call, no file). Results go to eval/results/planted-*.json, apart
from the eval's score files. They hold back-translations and judge notes of these drafts, never ticket text.
Exit codes: 0 done, 2 setup error (see agent/run.py).
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent import decide
from agent.checks import VERDICT_CHECKS, code_checks, model_checks
from agent.config import load_config
from agent.decide import ModelFailed, ModelSetupError
from agent.helpdesk import Helpdesk, HelpdeskError
from agent.rules import screen
from agent.run import prompt_version
from eval.run_eval import RESULTS, git_state
from eval.score import judge_names

VARIANTS = Path(__file__).with_name("planted_variants.json")


def load(path=VARIANTS):
    return json.loads(path.read_text(encoding="utf-8"))


def versions(spec):
    """Each example's control, then its planted versions, as dicts ready to check."""
    for ex in spec["examples"]:
        base = {"example": ex["example"], "english": ex["english"], "faq_ids": ex["faq_ids"]}
        yield {**base, "id": f"{ex['example']}-control", "kind": "control", "dutch": ex["dutch"], "pattern": None,
               "other_patterns": {p["id"]: p["pattern"] for p in ex["planted"]}}
        for p in ex["planted"]:
            yield {**base, "id": p["id"], "kind": p["kind"], "dutch": ex["dutch"].replace(p["old"], p["new"], 1),
                   "pattern": p["pattern"], "other_patterns": {}}


def problems(spec):
    """What is wrong with the variants file, as plain sentences; [] if it is usable."""
    out = []
    for ex in spec["examples"]:
        for p in ex["planted"]:
            if ex["dutch"].count(p["old"]) != 1:
                out.append(f"{p['id']}: the edit's old text must occur exactly once in the draft")
            if p["old"] == p["new"]:
                out.append(f"{p['id']}: the edit changes nothing")
            if re.search(p["pattern"], ex["english"], re.IGNORECASE):
                out.append(f"{p['id']}: the pattern already matches the honest English")
    return out


def check_version(v, ticket_text, plan):
    """One version through the agent's checks. Returns (row, usages). The row holds names, flags and the texts
    the judge compared for this draft (back-translation, notes); never the ticket."""
    code = code_checks(v["dutch"], "nl", ticket_text)
    row = {"id": v["id"], "example": v["example"], "kind": v["kind"],
           "code_failed": sorted(k for k, val in code.items() if val), "judge_failed": None,
           "shown_in_back": None, "control_pattern_hits": None, "back_translation": None, "judge_notes": [],
           "error": None}
    if row["code_failed"]:
        return row, []
    reading = {}
    try:
        found, usages = model_checks(v["dutch"], v["english"], v["faq_ids"], ticket_text, plan, reading=reading)
    except ModelFailed as e:
        return {**row, "error": f"model_failed: {e}"}, []
    back = reading.get("back_translation")
    row.update(judge_failed=judge_names({"model": found}), back_translation=back,
               judge_notes=[p for p in found if p not in VERDICT_CHECKS])
    if back is not None and v["pattern"]:
        row["shown_in_back"] = bool(re.search(v["pattern"], back, re.IGNORECASE))
    if back is not None and v["other_patterns"]:
        row["control_pattern_hits"] = sorted(i for i, pat in v["other_patterns"].items()
                                             if re.search(pat, back, re.IGNORECASE))
    return row, usages


def caught(row):
    return bool(row["code_failed"]) or bool(row["judge_failed"]) or row["error"] is not None


def summary(rows):
    """Counts over all runs: planted versions by outcome, and the controls' false alarms."""
    planted = [r for r in rows if r["kind"] != "control"]
    controls = [r for r in rows if r["kind"] == "control"]
    judged = [r for r in planted if not r["code_failed"] and r["error"] is None]
    return {
        "planted": len(planted),
        "reached_customer": sum(not caught(r) for r in planted),
        "stopped_by_code": sum(bool(r["code_failed"]) for r in planted),
        "judged": len(judged),
        "held_by_judge": sum(bool(r["judge_failed"]) for r in judged),
        "shown_in_back": sum(r["shown_in_back"] is True for r in judged),
        "judge_names": {n: sum(n in (r["judge_failed"] or []) for r in judged)
                        for n in VERDICT_CHECKS + ("check_call_failed",)
                        if any(n in (r["judge_failed"] or []) for r in judged)},
        "controls": len(controls),
        "control_false_alarms": sum(caught(r) for r in controls),
        "control_pattern_hits": sum(bool(r["control_pattern_hits"]) for r in controls),
        "errors": sum(r["error"] is not None for r in rows),
    }


def main(argv=None):
    args = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    args.add_argument("--runs", type=int, default=3)
    args.add_argument("--code-only", action="store_true")
    a = args.parse_args(argv)
    spec = load()
    bad = problems(spec)
    if bad:
        print("\n".join(bad))
        return 2
    try:
        hd = Helpdesk(load_config())
        try:
            tickets = {e["id"]: e for e in hd.examples()}
        finally:
            hd.close()
    except HelpdeskError as e:
        print(f"setup error: {e}")
        return 2
    context = {}
    for ex in spec["examples"]:
        subject, body, _ = screen(tickets[ex["example"]])
        context[ex["example"]] = (f"{subject}\n{body}", tickets[ex["example"]].get("customer_plan") or "unknown")

    if a.code_only:
        for v in versions(spec):
            code = code_checks(v["dutch"], "nl", context[v["example"]][0])
            print(f"  {v['id']:<18} code_failed={sorted(k for k, val in code.items() if val)}")
        return 0

    rows, cost = [], 0.0
    try:
        for run in range(1, a.runs + 1):
            for v in versions(spec):
                row, usages = check_version(v, *context[v["example"]])
                row["run"] = run
                cost += sum(u["cost_usd"] for u in usages)
                rows.append(row)
                print(f"  r{run} {v['id']:<18} code={row['code_failed']} back_shows={row['shown_in_back']} "
                      f"judge={row['judge_failed']}" + (f" control_pattern_hits={row['control_pattern_hits']}"
                                                         if row["control_pattern_hits"] else ""))
    except ModelSetupError as e:
        print(f"setup error: {e}")
        return 2
    git, dirty = git_state()
    s = summary(rows)
    out = {"date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git": git, "dirty": dirty,
           "prompt_version": prompt_version(), "check_model": decide.CHECK_MODEL, "runs": a.runs,
           "variants_sha256": hashlib.sha256(VARIANTS.read_bytes()).hexdigest()[:12],
           "summary": s, "cost_usd": round(cost, 6), "rows": rows}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RESULTS / f"planted-{stamp}-{git}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"summary: {s}\ncost ${round(cost, 6)}\nwrote {path}")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
