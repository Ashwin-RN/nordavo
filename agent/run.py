"""One command: python -m agent.run [--dry-run] [--show] [--ticket T001] [--limit N]

For each open ticket: mask -> rules -> model proposal -> code routing -> reply checks -> post -> log.

Safe to re-run. The helpdesk's open list is the to-do list: a handled ticket is never fetched again.
Exit code 0 means every ticket was handled; 1 means some are still open or the helpdesk was
unavailable (run again); 2 means a request was rejected as malformed or unauthorised and the run stopped.
"""
import argparse
import os
import sys
import time

from agent.checks import check_reply, detect_language
from agent.config import load_config
from agent.decide import ModelFailed, propose
from agent.helpdesk import AlreadyHandled, Helpdesk, HelpdeskError, Unavailable
from agent.route import empty_decision, route
from agent.rules import hard_rule_hits, is_empty, mask
from agent.runlog import RunLog

LOCK = ".run.lock"


def decide_ticket(ticket):
    """Everything up to the post. Returns (decision, log fields). Raises ModelFailed."""
    if is_empty(ticket):
        d = empty_decision()
        return d, {"model_calls": [], "checks": None}

    subject, k1 = mask(ticket.get("subject") or "")
    body, k2 = mask(ticket.get("body") or "")
    text = f"{subject}\n{body}"
    proposal, usage = propose(ticket, subject, body)
    d = route(proposal, hard_rule_hits(text), k1 | k2)
    calls, checks = [usage], None

    if d["action"] == "reply":
        passed, checks, usages = check_reply(d, text)
        calls += usages
        if not passed:
            failed = [name for name, problems in checks.items() if problems]
            d = {**d, "action": "handoff", "route_reason": "checks_failed:" + ",".join(failed),
                 "reason": d["reason"].replace("Answered from FAQ", "Draft from FAQ")
                 + f" The draft failed automatic checks ({', '.join(failed)}), so a human reviews it.",
                 "handoff_note": f"Automatic reply held back: failed checks {', '.join(failed)}.\n{d['handoff_note']}"}
    return d, {"model_calls": calls, "checks": checks}


def fallback_decision(ticket, error):
    """Model failed twice: hand off so the ticket is not left behind."""
    body = mask(ticket.get("body") or "")[0]
    return {
        "action": "handoff", "language": detect_language(body) or "nl", "category": "other", "priority": "P3",
        "reason": "Automatic triage failed, so a human triages this ticket.", "route_reason": "model_failed",
        "handoff_note": f"Automatic triage failed ({error}). Please read and triage this ticket manually.",
        "flags": [],
    }


def show(ticket, d, extra):
    """Print the decision to the screen (never to the log): for dry runs and live demos."""
    print(f"--- {ticket['id']} | {ticket.get('subject')}\n    {d['action']} {d['language']} {d['category']} "
          f"{d['priority']} ({d['route_reason']})\n    reason: {d['reason']}")
    for key in ("draft_reply", "draft_english", "handoff_note"):
        if d.get(key) and (key != "draft_english" or d["action"] == "reply"):
            print(f"    {key}: " + d[key].replace("\n", "\n      "))
    failed = {k: v for k, v in (extra.get("checks") or {}).items() if v}
    if failed:
        print(f"    failed checks: {failed}")


def handle(hd, log, ticket, dry_run, decision=None, extra=None, verbose=False):
    """Decide (unless given), post, and write one log line. Returns the outcome string."""
    started = time.monotonic()
    hd.http_log = []
    if decision is None:
        decision, extra = decide_ticket(ticket)
    if verbose:
        show(ticket, decision, extra)
    outcome, error = "dry_run", None
    if not dry_run:
        try:
            outcome = hd.send(ticket["id"], decision["action"], decision)
        except AlreadyHandled:
            outcome = "already_handled"   # someone else answered it; never retry
        except Unavailable as e:
            outcome, error = "left_open", str(e)
    calls = extra.get("model_calls", [])
    log.write(
        ticket_id=ticket["id"], action=decision["action"], outcome=outcome,
        language=decision["language"], category=decision["category"], priority=decision["priority"],
        confidence=decision.get("confidence"), rule_flags=decision.get("flags", []),
        faq_ids=decision.get("faq_ids", []), route_reason=decision["route_reason"], checks=extra.get("checks"),
        model_calls=calls, cost_usd=round(sum(c["cost_usd"] for c in calls), 6),
        latency_s=round(time.monotonic() - started, 2), http=hd.http_log, error=error, dry_run=dry_run,
    )
    return outcome


def _pid_alive(pid):
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_lock():
    """One run at a time. A lock left by a crashed run (its process is gone) is taken over."""
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                pid = int(open(LOCK).read().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _pid_alive(pid):
                sys.exit(f"Another run (pid {pid}) is active. Wait for it to finish.")
            print(f"Taking over a lock left by a crashed run (pid {pid}).")
            os.remove(LOCK)
    sys.exit(f"Could not take {LOCK}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Roosterly support ticket agent")
    ap.add_argument("--dry-run", action="store_true", help="decide and log, but post nothing")
    ap.add_argument("--ticket", help="handle only this ticket id")
    ap.add_argument("--limit", type=int, help="handle at most this many tickets")
    ap.add_argument("--show", action="store_true", help="print each decision and draft to the screen (not the log)")
    args = ap.parse_args(argv)

    take_lock()

    hd = Helpdesk(load_config())
    log = RunLog()
    try:
        status = hd.status()
        print(f"mode={status['mode']} open={status['open_tickets']} handled={status['handled_tickets']} "
              f"log={log.path}{' DRY RUN' if args.dry_run else ''}")

        tickets = [hd.get_ticket(args.ticket)] if args.ticket else list(hd.open_tickets())
        tickets = [t for t in tickets if not t.get("handled")][: args.limit]
        failed = []
        for t in tickets:
            try:
                outcome = handle(hd, log, t, args.dry_run, verbose=args.show)
            except ModelFailed as e:
                failed.append((t, str(e)))
                print(f"{t['id']}: model failed ({e}); will retry once at the end")
                continue
            print(f"{t['id']}: {outcome}")

        for t, first_error in failed:                       # pass 2
            try:
                outcome = handle(hd, log, t, args.dry_run, verbose=args.show)
            except ModelFailed as e:
                d = fallback_decision(t, e)
                outcome = handle(hd, log, t, args.dry_run, decision=d, extra={"model_calls": []}, verbose=args.show)
            print(f"{t['id']}: {outcome} (second pass)")

        if args.dry_run or args.ticket or args.limit:
            return 0
        left = hd.status()["open_tickets"]
        print(f"done: {left} tickets still open")
        return 1 if left else 0
    except Unavailable as e:                                # outage while listing: nothing lost
        print(f"stopped: the helpdesk is unavailable ({e}). Nothing was lost; run again later.", file=sys.stderr)
        return 1
    except HelpdeskError as e:
        print(f"stopped: the helpdesk rejected a request ({e}). Fix the cause and run again.", file=sys.stderr)
        return 2
    finally:
        log.close()
        hd.close()
        os.remove(LOCK)


if __name__ == "__main__":
    sys.exit(main())
