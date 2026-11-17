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

## Talking to the helpdesk

The API reference says what each error means. These are the choices it leaves open.

| Decision | Why | What it costs |
|---|---|---|
| Retry 503s up to 6 times, the wait doubling up to 8 seconds, with a little random jitter | Rides out a short outage without hanging | About 15 seconds per ticket in a long outage (a circuit breaker is the next step) |
| At most 4 calls a second, under the limit of 5 | A margin means we almost never see a 429 | Slightly slower runs |
| On a timeout, look the ticket up before sending again | A timeout means "maybe saved"; resending blind could cause a 409 | One extra call, only after a timeout |
| The helpdesk's open list is the only record of what is done | A local list can drift: a crash between the helpdesk saving and our list updating would cause a resend | 3 calls to list the tickets each run |
| Retries run out: leave the ticket open and carry on | Nothing is lost; the next run picks it up | Customers wait during an outage |
| The log takes only named fields, each line written to disk at once | Ticket text cannot leak in by accident; a crash loses one line at most | A new field has to be added to the list on purpose |

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
