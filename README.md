# Roosterly support agent

Replies from the FAQ, hands off to a human, or closes each ticket, using Claude Haiku 5.5. Detail: [DECISIONS.md](DECISIONS.md) and [eval/review/](eval/review/).

## How to run

Python 3.12.

```
git clone https://github.com/Ashwin-RN/nordavo && cd nordavo
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                # then fill in the keys
python -m agent.run --dry-run --ticket T001 --show  # preview, posts nothing
python -m agent.run                                 # live: every open ticket
python -m eval.run_eval --repeat 3                  # eval on the 10 examples
```

## Decisions

1. **The model proposes; code decides whether to post**, masking payment details and sending the client's hard rules to a human by keyword, because only code applies a rule every time.
2. **Dutch is drafted directly** to keep the FAQ's exact menu labels; a call that sees only the draft back-translates it, and a judge compares that with the drafter's English and the cited FAQ entries.
3. **Unsure goes to a human** (confidence under 0.7, not fully answered by the FAQ, a rule flag, a failed check), because a wrong reply or close is harder to undo than a handoff.

**Assumed** (all nine in [DECISIONS.md](DECISIONS.md#assumptions-where-the-brief-was-unclear)): "how do I upgrade?" is self-service, not a contract change; text instructing the AI goes to a human with no priority floor, so asking for P1 does not earn one; a reply needs confidence 0.7 or more.

**AI tools**: built with Claude Code (Claude Opus 5.5): design talked through step by step, code written with it, each layer explained back to me before commit. A second model reviewed each layer against the brief; findings were fixed or listed as gaps. Opus also wrote the blind readings of the Dutch drafts and the planted errors in `eval/`; no Dutch speaker has checked them.

## Reliability

**503**: up to 6 attempts, the wait doubling to 8 s, then the ticket stays open for the next run. **429**: at most 4 calls a second (limit 5); Retry-After honoured. **409**: skipped, never retried; after an ambiguous timeout the ticket is looked up before resending. **Crash**: the open list is the only record; killed after 7 tickets, the re-run handled the other 23, no duplicates (tested on the 17 Nov code, not re-run on the final code). **Security**: common card and IBAN formats masked before the model ([gaps](DECISIONS.md#left-out-on-purpose-gaps)); text instructing the AI goes to a human; keys from environment variables or a git-ignored `.env`; the log never holds ticket text.

## Eval and fix

On E07 the judge, shown only the FAQ entries the drafter cites, held a reply that used an uncited entry. Fix: cite every entry a fact comes from. That removed one cause rather than fixing E07: the drafter dropped the unasked-for detail instead of citing it, the uncited-entry hold went from 4 of 6 runs to 0 of 3, and E07 replied 2 of 3 times (the third was held by the plan check). Over 3 runs of the 10 examples: all four fields right 16/30 → 23/30; replies on reply-labelled cases 8/18 → 13/18; no wrong closes in 30 decisions and no replies in the 12 labelled handoff or close, a small base. E07 is two of the five extra replies; the rest varied across runs, and the fix was chosen on these examples.

**Cost**: 139,055 input tokens × $0.10/M + 22,653 output × $0.50/M = $0.0252 for 30 tickets, **about $0.084 per 100** on the eval mix. [Final run](logs/run-20261118T192429Z.jsonl): 30 handled (8 replies, 20 handoffs, 2 closes), $0.024, so $0.080 per 100.

## What I would improve

**Next step**: the judge still held 4 of 17 drafts for reply-labelled cases (I have not checked which holds were right), and my planted errors only tested Dutch and English disagreeing. Build fresh labelled Dutch cases, including drafts wrong in both languages, and measure false holds and missed errors separately before tuning. Then screen handoff notes for payment details and hand off spam verdicts with a high priority. The keyword lists were written after reading the practice tickets, so their recall is overstated.

**Rule to change**: "contract changes always go to a human" should say whether a self-service how-to counts; I answered "how do I upgrade?" from the FAQ (T023).
