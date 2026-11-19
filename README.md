# Roosterly support agent

Replies from the FAQ, hands off to a human, or closes each ticket, using Claude Haiku 5.5. Detail: [DECISIONS.md](DECISIONS.md) and [eval/review/](eval/review/).

## How to run

Python 3.12. Copy `.env.example` to `.env` and fill it in.

```
pip install -r requirements.txt
python -m agent.run --dry-run --ticket T001 --show  # preview, posts nothing
python -m agent.run                                 # live: every open ticket
python -m eval.run_eval --repeat 3                  # eval on the 10 examples
```

## Decisions

1. **The model proposes; code decides whether to post**, masking payment details and sending the client's hard rules to a human by keyword, because only code applies a rule every time.
2. **Dutch is drafted directly** to keep the FAQ's exact menu labels; a call that sees only the draft back-translates it, and a judge compares that with the drafter's English and the cited FAQ entries.
3. **Unsure goes to a human** (confidence under 0.7, not fully answered by the FAQ, a rule flag, a failed check), because a wrong reply or close is harder to undo than a handoff.

Assumed: "how do I upgrade?" is self-service, not a contract change. Built with Claude Code (Claude Opus 5.5), each layer explained back before commit; Opus also reviewed the Dutch, not a Dutch speaker.

## Reliability

**503**: up to 6 attempts, the wait doubling to 8 s, then the ticket stays open for the next run. **429**: at most 4 calls a second (limit 5); Retry-After honoured. **409**: skipped, never retried; after an ambiguous timeout the ticket is looked up before resending. **Crash**: the open list is the only record; killed after 7 tickets, the re-run handled the other 23, no duplicates. **Security**: common card and IBAN formats masked before the model ([gaps](DECISIONS.md#left-out-on-purpose-gaps)); text instructing the AI goes to a human; keys only in `.env`; the log never holds ticket text.

## Eval and fix

On E07 the judge, shown only the FAQ entries the drafter cites, held a reply that used an uncited entry. Fix: cite every entry a fact comes from; the drafter now drops the unasked-for detail and the hold is gone. Over 3 runs of the 10 examples: all four fields right 16/30 → 23/30; replies on reply-labelled cases 8/18 → 13/18; no wrong closes or replies to handoff cases. E07 is two of the five extra replies; the rest varied across runs, and the fix was chosen on these examples.

**Cost**: 139,055 input tokens × $0.10/M + 22,653 output × $0.50/M = $0.0252 for 30 tickets, **about $0.084 per 100**. [Final run](logs/run-20261118T192429Z.jsonl): 30 handled (8 replies, 20 handoffs, 2 closes), $0.024.

## What I would improve

**Next step**: the judge still held 4 of 17 good drafts, and my planted errors only tested Dutch and English disagreeing. Build fresh labelled Dutch cases, including drafts wrong in both languages, and measure false holds and missed errors separately before tuning. Then screen handoff notes for payment details and hand off spam verdicts with a high priority. The keyword lists were written after reading the practice tickets, so their recall is overstated.

**Rule to change**: "contract changes always go to a human" should say whether a self-service how-to counts; I answered "how do I upgrade?" from the FAQ (T023).
