# Blind review, part 2: Haiku's readings against mine (eval at b1e6d1c)

My readings were committed first (`blind-readings-b1e6d1c.md`, commit ba5737b). This file compares them with the
translations files committed in bcf72b8. Reviewer: Claude Opus 5.5, same vendor as the agent, not a native Dutch
speaker; no Dutch speaker has checked this. Counts, not rates: the sample is small.

## 1. Is Haiku's back-translation faithful?

| Dutch drafts | Same meaning as my reading | Minor wording only | Different meaning |
|---|---|---|---|
| 15 (E02, E04, E05, E07, E10 × 3 runs) | 15 | 15 (e.g. "functie" as "function", not "role"; "salarisintegraties" as "salary integrations") | 0 |

The back-translation said what the Dutch says in every case. E01's 3 English drafts are set apart: their
back-translation is the draft itself.

## 2. Did the translation-match check (`matches_reading_aid`) fire correctly?

It said no once: E04 r1. The drafter's English translated the menu names ("Offer swap", "Rota → Requests"); the
back-translation kept the Dutch ("Ruil aanbieden", "Rooster → Verzoeken"). Same meaning, so a **false alarm**: 1 of
15 Dutch drafts, and it cost a good reply. E04 r3 had the same pattern and passed, so the judge is not consistent
on it. On honest drafts this shows the check rarely misfires; it does not show it catches a real mismatch (that
needs planted errors).

## 3. Why the judge held the 10 replies it held (4 + 4 + 2 over the runs; all labelled "reply" by Nordavo)

| Example | Runs held | Judge's answer | Is the judge right? |
|---|---|---|---|
| E07 Plus for 25 employees | 3 of 3 | supported_by_faq: "the FAQ does not name Nmbrs, Loket.nl or AFAS" | **No.** F04 names all three. The judge sees only the entries the drafter cited (`faq_ids`), and its notes quote F05's wording ("the payroll integrations"), so F04 was not among them. Inferred: the eval rows do not record the cited ids |
| E10 maintenance tonight? | 3 of 3 | answers_the_question (r3 also supported_by_faq, no_promises) | Strict. The FAQ cannot say whether there is maintenance tonight; pointing to status.roosterly.nl is the answer Nordavo labels as a reply. r3's "always the most recent information" is a small claim beyond F11 |
| E01 iOS 15 crash (English) | 2 of 3 | supported_by_faq: "the FAQ does not say iOS 15 causes crashes" | Strict. The FAQ gives iOS 16 as the minimum; "most likely why it crashes" is an inference, and Nordavo labels it a reply |
| E05 r2 Google Agenda idea | 1 of 3 | answers_the_question | Strict, and inconsistent: the same reply passed in r1 and r3 |
| E04 r1 | 1 of 3 | matches_reading_aid | False alarm (section 2) |

## 4. What no check can see

6 of 15 Dutch drafts have a small grammar or wording slip ("ons publieke roadmap" for "onze", "onbeperkt aantal"
without "een", "er op" for "erop", an awkward "het wijzigt vanaf de volgende facturen"). None changes the meaning,
so the back-translation and the judge pass them by design. Catching these needs a Dutch reader or a grammar model.

## What this says

- The translation step works on these drafts: 15 of 15 faithful.
- Every reply lost in the baseline was lost to the judge, never to the translation, and in E07 the judge was wrong
  because it was not shown the FAQ entry the draft used.
- The one reliable, repeatable loss is E07 (3 of 3, one cause): the fix candidate for the eval.
