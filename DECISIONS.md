# Decisions

Plain-English record of what was chosen, why, and what it costs. Updated as the work goes.
The README's "Decisions" and "What I would improve" sections are written from this file.

## The ground

| Decision | Why | What it costs |
|---|---|---|
| The model proposes, code decides | A model can be talked into things by a ticket; code cannot. Every safety rule lives in code. | More code to write and test |
| One model call per ticket for triage | Small and easy to explain. Replies get two more calls to check them. | Replies cost about 3x a handoff |
| Work in Dutch directly, with an English version of each reply alongside | Translating first loses the exact Dutch menu names customers see | We need checks that do not depend on reading Dutch |
| Claude Haiku 5.5 | Cheap enough to stay far under the €1 budget, good enough on the examples | A stronger model might score higher; the model is one setting to change |
| Python | Simple, and the reviewer can read it | None worth noting |

## Assumptions (where the brief was unclear)

| Assumption | Why |
|---|---|
| Text that tries to instruct the AI (T007, T030) goes to a human as a possible security incident, and cannot raise its own priority | Otherwise the attacker gets the P1 they asked for |
| A customer sending card details (T008) goes to a human, details masked | Asking us to change payment method is a contract change |
| "How do I upgrade?" (T023) is answered from the FAQ | A how-to about self-service is not a request for us to change the contract |
| GDPR requests are at least P2, not P1 | Nordavo's own example E09 labels one P2 |
| An empty ticket is closed with language "nl" | The API requires a language; most customers write Dutch |
| A reply needs the model's confidence at 0.7 or more | The brief leaves "unsure" open; this is one gate among several, and a setting |

## How AI tools were used

| What | How |
|---|---|
| Claude Code | Design talked through step by step, code written with it, every layer explained back before commit |
| Second-opinion review | A stronger model reviewed layers 1 to 5 against the brief; findings fixed or listed as gaps |

## Left out on purpose (gaps)

| Gap | Why it is left out | What I would do next |
|---|---|---|
