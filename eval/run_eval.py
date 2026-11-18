"""Eval on Nordavo's 10 labelled examples: python -m eval.run_eval [--repeat 3] [--show]

Fetches GET /examples (a read; nothing is posted) and runs each example through agent.run.decide_ticket,
the same path a live ticket takes up to the post. The label is removed before the agent sees the example.
Code scores language, category, priority and action against Nordavo's labels (eval/score.py).

Two files per run in eval/results/, both headed with date, git short hash (and whether the tree had
uncommitted changes), prompt_version and the two model names:
  eval-*.json          scores: ids, labels, predicted fields, pass/fail, failed check names, the judge's
                       failed answers by name, tokens and cost. Never ticket text, drafts or reasons.
  translations-*.json  text, on purpose: for each draft that got a back-translation, the draft, the
                       drafter's English, the independent back-translation and the judge's notes, so the
                       Dutch replies can be checked without trusting the judge. Nordavo's examples only.
--show prints what each failed code check found to the screen only (the judge's notes stay in the file).

Not held out: the triage prompt and the keyword lists were shaped while reading these examples, and
tests/test_checks.py and tests/test_rules.py use text from E01, E03, E04 and E07. This eval measures
the agent on cases it was built around; it overstates how it does on unseen tickets.

Exit codes: 0 done, 1 the helpdesk was unavailable (run again), 2 the model API or the helpdesk
rejected our setup.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent import decide
from agent.checks import VERDICT_CHECKS
from agent.config import load_config
from agent.decide import ModelFailed, ModelSetupError
from agent.helpdesk import Helpdesk, HelpdeskError, Unavailable
from agent.run import decide_ticket, prompt_version
from eval.score import FIELDS, across_runs, fmt_range, score_row, totals

RESULTS = Path(__file__).resolve().parent / "results"


def _git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False).stdout


def git_state(git=_git):
    """(short hash, dirty). Dirty means code differs from that commit; earlier results files do not count."""
    short = git("rev-parse", "--short", "HEAD").strip() or "unknown"
    changed = [line for line in git("status", "--porcelain").splitlines() if "eval/results/" not in line]
    return short, bool(changed)


def translation_entry(example_id, decision, extra, row):
    """Text for the translations file: the draft, its English, the back-translation and the judge's notes.
    Only for drafts that got a back-translation. Never in the scores file or the run log."""
    reading = (extra or {}).get("reading")
    if not reading:
        return None
    notes = [p for p in (extra.get("checks") or {}).get("model", []) if p not in VERDICT_CHECKS]
    return {"id": example_id, "language": decision["language"], **reading,
            "judge_failed": row["judge_failed"], "judge_notes": notes}


def run_once(examples, show=False):
    """Score every example once. Returns (rows, translation entries). ModelSetupError stops the eval."""
    rows, entries = [], []
    for ex in examples:
        ticket = {k: v for k, v in ex.items() if k != "label"}   # the agent never sees the label
        try:
            d, extra = decide_ticket(ticket)
            row = score_row(ex["id"], ex["label"], d, extra)
        except ModelFailed as e:
            d, extra, row = None, None, score_row(ex["id"], ex["label"], None, error=f"model_failed: {e}")
        rows.append(row)
        entry = translation_entry(ex["id"], d, extra, row)
        if entry:
            entries.append(entry)
        print_row(row)
        if show and extra and extra.get("checks"):
            # the judge's notes are in the translations file: on screen they would spoil a blind review
            failed = {k: v for k, v in extra["checks"].items() if v and k != "model"}
            if failed:
                print(f"      found (screen only): {failed}")
    return rows, entries


def print_row(row):
    mark = {True: "ok", False: "--"}
    pred = row["predicted"] or {}
    cells = "  ".join(f"{f}={row['label'][f]}/{pred.get(f, '-')}{'' if row['pass'][f] else '*'}" for f in FIELDS)
    print(f"  {row['id']} {mark[row['pass']['all']]}  {cells}  {row['route_reason'] or row['error']}"
          f"{'  checks=' + str(row['checks']) if row['checks'] else ''}")


def print_totals(t):
    n = t["n"]
    print(f"  fields: " + "  ".join(f"{f} {t[f]}/{n}" for f in FIELDS) + f"  all four {t['all']}/{n}")
    print(f"  action misses: unsafe {t['unsafe']}, lost work {t['lost_work']}, other {t['other_miss']}; "
          f"replies made {t['replies_made']} (right {t['replies_right']}) of {t['replies_labelled']} labelled; "
          f"model errors {t['model_errors']}")
    if "reached_judge" in t:   # older results files have no judge counts
        print(f"  judge: reached {t['reached_judge']}, said no: {t['judge_failed'] or 'none'}")
    print(f"  tokens in {t['tokens_in']} out {t['tokens_out']}, cost ${t['cost_usd']:.6f}, "
          f"${t['cost_per_100_usd']:.4f} per 100 tickets")


def print_ranges(summary):
    r = summary["ranges"]
    print(f"over {summary['runs']} runs (min-max): " + "  ".join(f"{k} {fmt_range(*r[k])}" for k in r))
    print(f"examples whose outcome changed between runs: {summary['flipped'] or 'none'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Eval on the 10 labelled examples")
    ap.add_argument("--repeat", type=int, default=1, help="run the eval this many times (the judge is noisy)")
    ap.add_argument("--show", action="store_true", help="print what failed checks found (screen only)")
    args = ap.parse_args(argv)

    hd = Helpdesk(load_config())
    try:
        examples = hd.examples()
    except Unavailable as e:
        print(f"stopped: the helpdesk is unavailable ({e}). Run again later.", file=sys.stderr)
        return 1
    except HelpdeskError as e:
        print(f"stopped: could not fetch /examples ({e})", file=sys.stderr)
        return 2
    finally:
        hd.close()

    RESULTS.mkdir(exist_ok=True)
    results = []
    for i in range(1, args.repeat + 1):
        short, dirty = git_state()
        started = datetime.now(timezone.utc)
        print(f"run {i}/{args.repeat}  git {short}{' (uncommitted changes)' if dirty else ''}  "
              f"prompt_version {prompt_version()}")
        try:
            rows, entries = run_once(examples, show=args.show)
        except ModelSetupError as e:
            print(f"stopped: the model API rejected our setup ({e})", file=sys.stderr)
            return 2
        header = {"date": started.isoformat(timespec="seconds"), "git": short, "dirty": dirty,
                  "prompt_version": prompt_version(), "triage_model": decide.MODEL, "check_model": decide.CHECK_MODEL}
        result = {**header, "totals": totals(rows), "rows": rows}
        # the run number keeps two runs that start in the same second from overwriting each other
        name = f"{started.strftime('%Y%m%dT%H%M%SZ')}-r{i}-{short}{'-dirty' if dirty else ''}.json"
        path = RESULTS / f"eval-{name}"
        path.write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        # the texts the judge compared, for a separate review (Nordavo's examples only); the scores file has none
        (RESULTS / f"translations-{name}").write_text(
            json.dumps({**header, "entries": entries}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print_totals(result["totals"])
        print(f"  wrote {path.relative_to(RESULTS.parent.parent)}")
        results.append(result)
    if len(results) > 1:
        print_ranges(across_runs(results))
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # Windows writes pipes and files in cp1252
        stream.reconfigure(encoding="utf-8")
    sys.exit(main())
