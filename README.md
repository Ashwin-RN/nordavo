# Roosterly support agent

Triages Roosterly's helpdesk on Claude Haiku 5.5: a reply from the FAQ, a handoff to a human with a note, or a close.
Every choice, its cost, and the gaps: [DECISIONS.md](DECISIONS.md).

## How to run

Python 3.12, from a fresh clone:

```
pip install -r requirements.txt
cp .env.example .env                  # helpdesk URL and key, your email, ANTHROPIC_API_KEY
python -m pytest -q                   # 223 tests, no network, no model
python -m agent.run --dry-run --show  # decides every open ticket, posts nothing
python -m agent.run                   # live: posts to the helpdesk
python -m eval.run_eval --repeat 3    # eval on GET /examples, posts nothing
python -m eval.planted --runs 3       # planted errors against the reply checks, posts nothing
```

Exit codes: 0 done, 1 run again, 2 fix the setup first. Safe to re-run: the helpdesk's open list is the to-do list.

## Decisions

1. **The model proposes, code decides.** Haiku fills a fixed form. Code masks payment details before the model sees
   the ticket, applies the client's hard rules by keyword (refund, cancellation, GDPR, security, legal, churn, text
   that instructs the AI: always a human), and routes.
2. **Dutch written directly, checked without trusting the drafter.** The drafter writes the reply and its own English
   version. A second call back-translates the Dutch seeing nothing else; a judge compares the two English versions
   and checks the reply against the cited FAQ entries and the customer's plan.
3. **Unsure means a human**: confidence under 0.7, a question the FAQ does not fully answer, a rule flag, or any
   failed check.

Assumed where the brief was open: text that instructs the AI is a security incident; "how do I upgrade?" is
self-service, not a contract change; GDPR is P2, as in E09; other languages go to a human.

AI tools: built with Claude Code (Claude Opus 5.5), each layer explained back before commit. The Dutch review and
planted errors below are by Opus too: a stronger model, same vendor, no Dutch speaker. No temperature is set (Haiku 5.5
rejects a non-default one), so the eval measures variation over 3 runs. No retrieval: the whole FAQ fits in the prompt.

## Reliability

- **503**: up to 6 retries, the wait doubling to 8 s, then the ticket stays open for the next run. Seen once live
  (T019, final run, saved on retry).
- **429**: at most 4 calls a second against a limit of 5; on a 429, wait Retry-After.
- **409**: never retried. After a timeout the ticket is looked up before resending, so we never cause one.
- **Crash**: the open list is the only record; a lock stops two runs at once. Crash test (`logs/`, 17 Nov): killed
  after 7 tickets, the re-run handled the other 23, no duplicates.
- **Security**: cards and IBANs masked before the model sees them, and a reply holding any is held; keys only in `.env`; the log holds named
  fields, never ticket or reply text (tests push a marker through and check it is absent).

## Eval and fix

Nordavo's 10 labelled examples, 3 runs each ([eval/review/](eval/review/)):

| | Before (b1e6d1c) | After (3cc0210) |
|---|---|---|
| All four fields right | 4-6 of 10 | 7-8 |
| Unsafe actions | 0 | 0 |
| Replies made, of 6 labelled | 2-4 | 3-5 |

**Fix**: the judge sees only the FAQ entries the drafter cites. On E07 the drafter cited F05 for a fact from F04, so
the judge called it invented (held 4 of 6 runs). Now the drafter must cite every source entry. After: held 0 of 3,
because the drafter drops the uncited fact: one cause removed. The rest of the gain is judge noise, and the fix was
chosen on the examples it is scored on.

**Cost per 100 tickets**: after-fix eval, 30 tickets: 139,055 input tokens × $0.10/M + 22,653 output × $0.50/M =
$0.0252, so **about $0.084**. Final run: $0.024 for 30 tickets (8 replies, 20 handoffs, 2 closes, 0 errors).

**Dutch check**: the back-translation was faithful on 15 of 15 drafts (blind review); 48 of 48 planted one-word errors
in the Dutch, with the honest English kept, were held, against 0 of 12 honest drafts.

## What I would improve

**Next step**: the judge holds good replies (4 of 17 reply-labelled drafts after the fix). Grow the labelled set, ask
the judge twice and hold only if both say no, and have a Dutch speaker spot-check replies. Also: the keyword lists were
written after reading the practice tickets, so their recall here is overstated.

**One rule to change**: "contract changes always go to a human" should say whether a self-service how-to ("how do I
upgrade?") counts. I assumed it does not.
