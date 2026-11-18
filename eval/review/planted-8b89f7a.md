# Planted errors: do the checks catch a Dutch reply that differs from its English? (rig at 8b89f7a)

Variants, patterns and the meaning of "caught" were committed in 8b89f7a before the run; results in
`eval/results/planted-20261118T191904Z-8b89f7a.json`. prompt_version 5f2ce683, check model claude-haiku-5-5.

Setup: 4 honest Dutch drafts that passed the judge (E02, E04, E07, E10, eval r1 after the fix). For each, 4 versions
with one edit in the Dutch only (a negation, a wrong fact or number, a wrong time, a wrong actor or place); the
drafter's honest English is kept, which is what a reader without Dutch would see. Each version and the unchanged
draft (control) went through the agent's own checks, 3 runs.

| | Count |
|---|---|
| Planted versions checked (16 × 3 runs) | 48 |
| Stopped by a code check | 0 (the edits keep valid labels and URLs; the €175 edit passed only because of the number gap below) |
| Back-translation showed the planted meaning (pattern written in advance) | 48 of 48 |
| Held by the judge | 48 of 48 |
| ... of which `matches_reading_aid` (Dutch and English differ) | 48 |
| ... also `supported_by_faq` / `no_promises_beyond_faq` / `answers_the_question` | 42 / 14 / 10 |
| ... held by `matches_reading_aid` alone (no other answer said no) | 5 (E02-negation r1, E04-wrong_fact r2 and r3, E10-time r1 and r2) |
| **Would have reached a customer** | **0 of 48** |
| Controls held (false alarms) | 0 of 12 |
| Controls whose back-translation matched a planted pattern | 0 of 12 |
| Cost | 0.020479 USD |

## What it shows and what it does not

- The independent back-translation carried every planted change into English, and the comparison with the
  drafter's English caught every one, in every run. In 5 of 48 the comparison was the only answer holding the
  reply: without the back-translation those would have reached the customer.
- The results file holds no ticket text: no run of six words from the four ticket bodies appears in it (checked as
  a yes/no count). The judge's notes are free text from a call that saw the ticket, so this is checked, not
  guaranteed by the code.
- Limits, stated plainly:
  - The errors were written by Claude Opus 5.5 (same vendor as the agent), not a native Dutch speaker.
  - They are clear one-edit meaning changes. They do not test the subtler slips Haiku itself might make and then
    read past (same-model bias): that needs errors from the drafter's own outputs, or a second engine.
  - Every planted version makes the Dutch disagree with the English, so this tests the comparison. A draft wrong
    in both languages rests on the FAQ check alone; the 42 of 48 `supported_by_faq` answers are not evidence for
    that, since the judge had already seen the mismatch.
  - Counts, not rates: 16 errors on 4 drafts.
  - Grammar is out of scope: the 6 of 15 baseline grammar slips pass every check by design.
- Found on the way: the code number check allows any FAQ number times a ticket number (meant for 25 × €6), so a
  wrong total like €175 (7 × 25) passes it; the model checks caught it 3 of 3.
