# Blind readings of the baseline drafts (eval at b1e6d1c, results in bcf72b8)

Reviewer: Claude Opus 5.5, in the build session. A stronger model from the same vendor as the agent (Haiku 5.5);
not a native Dutch speaker, and no Dutch speaker has checked this. Written from `python -m eval.blind` output only
(id, run, language, draft), before opening the drafter's English, Haiku's back-translation or the judge's notes.
This file is committed before those are read; the comparison comes in a later commit.

Rubric, fixed before reading:
- **Meaning**: my English reading of each draft, sentence by sentence.
- **Fidelity** (scored later): does Haiku's back-translation say the same as my reading? same / minor wording / different meaning.
- **Dutch** (scored now): grammar or wording a native reader would notice. A back-translation cannot show this:
  it reports meaning, so a correct meaning in clumsy Dutch passes every check.

E01 is English (3 drafts): its back-translation is trivial, so it is counted apart and not read here.

## Readings

| Draft | My English reading | Dutch issues I see |
|---|---|---|
| E02 r1 | Good day, you can change the VAT number yourself under Instellingen → Bedrijfsgegevens (Settings → Company details). The change applies to future invoices. Kind regards, Team Roosterly | none |
| E02 r2 | Dear Sir/Madam, thank you for your message. You can change the new VAT number yourself under Instellingen → Bedrijfsgegevens. It changes from the next invoices on. Team Roosterly | "Het wijzigt vanaf de volgende facturen" is awkward ("it changes from the next invoices"); natural: "De wijziging geldt vanaf de volgende factuur". "Beste," with no name is curt |
| E02 r3 | Good day, you can change the new VAT number yourself under Instellingen → Bedrijfsgegevens. The change applies to future invoices. If you have any questions after that, we are glad to hear from you. Kind regards, Team Roosterly | none |
| E04 r1 | Hi, you open the shift in the app and tap "Ruil aanbieden" (Offer swap). A colleague with the same role can then accept the swap. After that the manager approves the swap under Rooster → Verzoeken (Schedule → Requests). Good luck! Team Roosterly | none |
| E04 r2 | Same as r1, with "your manager" instead of "the manager". | none |
| E04 r3 | Same as r2, without "then", and "Regards" instead of "Good luck!". | none |
| E05 r1 | Thank you for your idea to connect Roosterly with Google Calendar. We read every suggestion. You can view the idea on our public board roadmap.roosterly.nl and vote on it. Unfortunately we cannot promise a delivery date. Team Roosterly | "er op stemmen" is written "erop stemmen". "You can view the idea" implies their idea is already on the board, which the FAQ does not say |
| E05 r2 | Thanks for your idea. We read every request, and you can view it on our public roadmap and vote via roadmap.roosterly.nl. Unfortunately we cannot promise a delivery date. Team Roosterly | "ons publieke roadmap" should be "onze publieke roadmap" (roadmap is a de-word). Same "view it" implication |
| E05 r3 | Thank you for your idea. We read every idea, and you can find it on our public roadmap at roadmap.roosterly.nl, where you can vote on ideas. Unfortunately we cannot promise a delivery date for individual requests. Team Roosterly | "ons publieke roadmap" should be "onze". Uses formal "u", the others informal "je": both are fine, but inconsistent across runs |
| E07 r1 | Hello, Plus costs €6 per active employee per month, excluding VAT. For 25 employees that comes to €150 per month, excluding VAT. Plus includes an unlimited number of locations, API access and the payroll integrations (Nmbrs, Loket.nl and AFAS). If you have any questions, we are glad to hear from you. Team Roosterly | "bevat onbeperkt aantal vestigingen" misses an article: "een onbeperkt aantal" |
| E07 r2 | Good day, Plus costs €6 per active employee per month, excl. VAT. For 25 employees that comes to €150 per month excl. VAT, if all 25 employees are active. Plus offers unlimited locations, API access and the payroll integrations with Nmbrs, Loket.nl and AFAS. Team Roosterly | none |
| E07 r3 | Hello, Plus costs €6 per active employee per month, excl. VAT. For 25 employees that comes to €150 per month, excl. VAT. Plus also includes unlimited number of locations, API access and the payroll integrations with Nmbrs, Loket.nl and AFAS. Team Roosterly | "onbeperkt aantal" misses "een", as in r1 |
| E10 r1 | Hi, current outages and planned maintenance can be seen at status.roosterly.nl. There you will find the most recent information. Team Roosterly | none |
| E10 r2 | Hi, you can see current outages and planned maintenance at status.roosterly.nl. Team Roosterly | none |
| E10 r3 | Hi, you can see current outages and planned maintenance at status.roosterly.nl. There you will always find the most recent information. Team Roosterly | none |

## Counts (Dutch drafts only)

- 15 distinct Dutch drafts read (E02, E04, E05, E07, E10, 3 runs each); 3 English drafts (E01) set apart.
- Meaning: every draft reads as a plain, on-topic answer; none says something I would call wrong in Dutch.
- Dutch issues: 6 of 15 drafts have a small grammar or wording slip (E02 r2, E05 r1, E05 r2, E05 r3, E07 r1,
  E07 r3). None changes the meaning. No check in the agent can see these: the back-translation
  carries meaning, not grammar.
