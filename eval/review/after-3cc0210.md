# After the fix: eval at 3cc0210 (prompt_version 5f2ce683), results in 7b45f51

The fix (3cc0210): the drafter is told to cite every FAQ entry a fact comes from, because the judge is shown only
the cited entries. The only change under `agent/` since the baseline (`git diff b1e6d1c..3cc0210 -- agent/`).
Ids, codes and counts only. Counts, not rates: 10 examples, 3 runs each.

## How to read these results

- 30 decisions = Nordavo's 10 labelled examples × 3 runs; the judge varies between runs, so ranges, not one number.
- An action match compares the agent's action (reply, handoff, close) with Nordavo's label; it says nothing about
  the reply's wording. "Unsafe" means a wrong close, or a reply where the label hands off: 0 before and after.
- Raw files: `eval/results/eval-*-b1e6d1c.json` (before), `eval-*-3cc0210.json` (after), with the texts the judge
  compared in the matching `translations-*` files. The 48 planted checks (`planted-8b89f7a.md`) test Dutch-English
  disagreement only.

## Per example: replies out of 3, and what the judge said no to

| Example | Label | Before (b1e6d1c) | After (3cc0210) |
|---|---|---|---|
| E01 iOS 15 crash (en) | reply | 1/3; supported_by_faq ×2 | 0/3; r1 stopped by the code `language` check, r2 supported_by_faq + no_promises, r3 supported_by_faq |
| E02 VAT number | reply | 3/3 | 3/3 (r1 priority P3 for P4, so it shows as flipped) |
| E03 | handoff | 0/3, never judged | 0/3, never judged |
| E04 shift swap | reply | 2/3; matches_reading_aid ×1 (false alarm) | 3/3 |
| E05 Google Agenda idea | reply | 2/3; answers_the_question ×1 | 3/3 |
| E06, E08, E09 | handoff / close / handoff | never judged | never judged |
| E07 Plus for 25 | reply | 0/3; supported_by_faq ×3 | 2/3; r2 fits_customer_plan |
| E10 maintenance tonight? | reply | 0/3; answers_the_question ×3 | 2/3; r2 answers_the_question |

## E07, the example the fix was for

| | Before (6 runs: 3 baseline + 3 follow-up) | After (3 runs) |
|---|---|---|
| F04 cited | 0 of 3 (follow-up runs; the baseline rows did not record ids) | 0 of 3 |
| Draft names Nmbrs, Loket.nl or AFAS | 3 of 3 baseline drafts | 0 of 3 (r2 mentions integrations in general) |
| Held on supported_by_faq | 4 of 6 | 0 of 3 |
| Replies | 2 of 6 | 2 of 3 |

- The ticket does not ask about payroll or integrations (keyword check, printed as yes/no only).
- So the drafter obeyed the new rule by leaving out the fact it could not cite, not by citing F04. That was not
  in the reading agreed beforehand; the user chose to keep the fix as is. Call it one cause removed, not "fixed".
- r2's hold: the judge wanted the reply to say a Basis customer must upgrade, though the customer asked for the
  Plus price. Strict.

## Totals

| | Before | After |
|---|---|---|
| All four fields right | 4-6 of 10 | 7-8 of 10 |
| Action right | 6-8 | 7-9 |
| Unsafe | 0 | 0 |
| Lost work | 2-4 | 1-3 |
| Replies made (all right), of 6 labelled | 2-4 | 3-5 |
| Drafts for reply-labelled tickets held by the judge | 10 of 18 | 4 of 17 (one stopped by code first) |
| Cost per 100 tickets | 0.0865-0.0901 USD | 0.0796-0.0898 USD |

A one-line fix aimed at E07 can move "all four" by at most one per run. The rest of the gain (E04, E05, E10) is
the judge's noise on other examples, not the fix.

## Cost per 100 tickets, the calculation

Haiku 5.5: 0.10 USD per million input tokens, 0.50 USD per million output tokens. After-fix runs, 30 tickets:
139,055 in × 0.10/1M = 0.013906; 22,653 out × 0.50/1M = 0.011327; sum 0.025232 USD (the files sum per call:
0.025234). Per ticket 0.000841, so **about 0.084 USD per 100 tickets** (range over the runs 0.0796-0.0898).
Replies cost more than handoffs (two extra check calls), so the figure moves with the share of replies.
