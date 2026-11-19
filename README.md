# Roosterly support agent

Each ticket gets a reply from the FAQ, a handoff to a human, or a close. Claude Haiku 5.5 proposes; code decides.
Trade-offs and known gaps: [DECISIONS.md](DECISIONS.md).

## How to run

Python 3.12. Copy `.env.example` to `.env` and fill in the helpdesk URL and key, your email and `ANTHROPIC_API_KEY`.

```
pip install -r requirements.txt
python -m pytest -q                                # 223 tests, no keys needed
python -m agent.run --dry-run --ticket T001 --show # preview one ticket, posts nothing
python -m agent.run                                # live: every open ticket, once
python -m eval.run_eval --repeat 3                 # eval on Nordavo's 10 labelled examples
```

## Decisions

1. **The model proposes, code decides.** Haiku fills a fixed form; code masks payment details, sends the client's hard
   rules to a human by keyword, and routes. A ticket can talk a model into things, not code.
2. **Dutch is drafted directly, then read back blind.** Drafting in Dutch keeps the FAQ's exact menu labels. A second
   call back-translates the draft seeing nothing else; a judge compares that with the drafter's English and checks
   the cited FAQ entries and the customer's plan.
3. **Unsure goes to a human** (confidence under 0.7, not fully answered by the FAQ, a rule flag, a failed check): a
   wrong reply or close is harder to undo than a handoff.

Assumed: "how do I upgrade?" is self-service, not a contract change (others in DECISIONS.md). Built with Claude Code
(Claude Opus 5.5), each layer explained back before commit; Opus also wrote the Dutch review and planted errors, and
no Dutch speaker has checked them.

## Reliability

**503**: up to 6 attempts, the wait doubling to 8 s, then the ticket stays open for the next run (seen live once,
saved on retry). **429**: at most 4 calls a second against a limit of 5; Retry-After honoured. **409**: that ticket is
skipped, never retried; after an ambiguous timeout the runner checks whether the ticket was handled before resending.
**Crash**: the helpdesk's open list is the only record; killed after 7 tickets, the re-run handled the other 23, no
duplicates (`logs/`). **Security**: common card and IBAN formats masked before the model
([gaps](DECISIONS.md#left-out-on-purpose-gaps)); keys only in `.env`; the log never holds ticket or reply text.

## Eval and fix

On E07 a pricing reply used a payroll fact from an FAQ entry it did not cite, so the judge, shown only cited entries,
held it (4 of 6 runs). The fix: cite every entry a fact comes from. The drafter now drops the unasked-for payroll
detail; that hold went to 0 of 3, and the one E07 run still held came from the plan check.

Over 3 runs of the 10 examples ([review](eval/review/after-3cc0210.md)): all four fields right 16/30 → 23/30; replies
on reply-labelled cases 8/18 → 13/18; zero wrong closes and zero replies to handoff cases, both times. E07 is 1 of the 7
extra matches and 2 of the 5 extra replies; the rest is judge noise, and the fix was chosen on these examples.

**Cost**: 139,055 input tokens × $0.10/M + 22,653 output × $0.50/M = $0.0252 for 30 tickets, **about $0.084 per
100**. [Final run](logs/run-20261118T192429Z.jsonl): 30 handled, 8 replies, 20 handoffs, 2 closes, $0.024.
[Planted errors](eval/review/planted-8b89f7a.md): 48 of 48 Dutch meaning changes held, 0 of 12 honest drafts.

## What I would improve

**Next**: measure false holds and missed factual errors separately on fresh Dutch cases, including drafts wrong in
both languages; the keyword lists were written after reading the practice tickets, so their recall is overstated.
**Rule to change**: "contract changes always go to a human" should say whether a self-service how-to counts.
