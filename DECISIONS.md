# Decisions

Plain-English record of what was chosen, why, and what it costs. Updated as the work goes.
The README's "Decisions" and "What I would improve" sections are written from this file.

## The ground

| Decision | Why | What it costs |
|---|---|---|
| The model proposes, code decides | A model can be talked into things by a ticket; code cannot. Every safety rule lives in code. | More code to write and test |
| One model call per ticket for triage | Small and easy to explain. Replies get two more calls to check them. | A reply costs about 1.35x a handoff (measured over 21 replies: triage $0.00078, back-translation $0.00008, judge $0.00019) |
| Work in Dutch directly, with an English version of each reply alongside | Translating first loses the exact Dutch menu names customers see | We need checks that do not depend on reading Dutch |
| Claude Haiku 5.5 | Cheap enough to stay far under the €1 budget, good enough on the examples | A stronger model might score higher; the model is one setting to change |
| Python | Simple, and the reviewer can read it | None worth noting |
| Exact versions in `requirements.txt`; settings checked before the run starts, a blank setting means its default | A fresh clone installs what was tested; a missing key is one clear line, not a crash mid-run | Updating a library is a deliberate edit |

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
| The log names the reply checks that failed, never what they found (`[]` = passed, `null` = no draft checked) | What a check found can quote the draft: a card number in a draft would be logged as digit groups | To see why a check failed, re-run the ticket with `--show` |

## Triage and routing

| Decision | Why | What it costs |
|---|---|---|
| The model returns a fixed form, never free text | Code can check every field; a broken form counts as a model failure | Each new field means a schema change |
| Routing order, first match wins: spam with no flags → close; any flag → handoff; not fully covered or unknown FAQ id → handoff; confidence under 0.7 → handoff; otherwise reply | Close is the one action no human sees again, so it has the strictest bar | Some answerable tickets go to a human |
| Confidence is one gate, never the only one | It is a number the model writes about itself, not a measured probability | None; the other gates check facts |
| Code writes the final reason | Code can override the model's action, so the reason must match what code chose | Reasons read a little templated |
| Model errors are sorted in one place: 400, 401, 403 and 404 mean our setup is wrong and stop the run (exit 2); anything else, including output that does not fit the form, is a model failure for that ticket | A bad key must stop the run, not turn into 30 fallback handoffs; rate limits and overloads are brief | A 400 tied to one ticket (e.g. far too long) would stop every run at that ticket |
| Each model call waits at most 40 seconds, and the SDK retries it 3 times | The slowest call seen is 8.6 s; the SDK's default wait is 10 minutes | A hung model costs about 2.7 minutes per ticket before it counts as failed |
| Circuit breaker: 3 model failures in a row, counted across both passes, stop the run (exit 1) with no fallback handoffs; a ticket whose model calls succeed resets the count | Three in a row means the model is down, not one ticket; fallbacks during an outage would hand all 30 tickets to a human at P3 | Three tickets that each fail for their own reasons in a row also stop the run, and the third gets no fallback |
| Model fails: retry once after the other tickets, then code writes a handoff | Failures are usually brief. A reply is unsafe without a proposal, and a close would bury the ticket. | The fallback is posted at P3 today, losing security floors (on the fix list) |
| One batch per command, as the brief asks | Tickets sit in a helpdesk queue | In production: run it every minute (safe to repeat), or use a webhook if the helpdesk offers one |

## The runner

| Decision | Why | What it costs |
|---|---|---|
| One run at a time, enforced by a lock file holding the run's process number; a lock whose process is dead is taken over | Two runs at once could answer the same ticket twice. Asking the operating system whether the process is alive needs no timer, so a slow but healthy run never loses its lock. | Works on one machine only; several machines need a shared lock with an expiry and a heartbeat |
| A tiny model call per model at start-up, after the helpdesk status and before any ticket is fetched, on every run including dry runs | A bad key or model name stops the run before any ticket is touched; a dry run with nothing open still proves the setup | One extra call per model per run, well under a hundredth of a cent |
| `--dry-run` posts nothing; `--show` prints drafts to the screen, never the log; `--dry-run --ticket` can re-check a ticket that is already handled | Drafts can contain names, and the logs are committed; re-checking one ticket shows why a draft failed without a reset | A re-check is a new model call, so its draft can differ from the one posted |
| Exit codes: 0 done, 1 run again, 2 fix the cause first | A scheduler or a person can tell "try later" from "something is wrong" | None |
| Tickets one at a time, not in parallel | 30 tickets take 2 to 3 minutes; running in order keeps crash recovery and the log simple | Slower on a large backlog (see gaps) |

## Assumptions (where the brief was unclear)

| Assumption | Why |
|---|---|
| Text that tries to instruct the AI (T007, T030) goes to a human as a possible security incident, and cannot raise its own priority | Otherwise the attacker gets the P1 they asked for |
| A customer sending card details (T008) goes to a human, details masked | Asking us to change payment method is a contract change |
| "How do I upgrade?" (T023) is answered from the FAQ | A how-to about self-service is not a request for us to change the contract |
| GDPR requests are at least P2, not P1 | Nordavo's own example E09 labels one P2 |
| A ticket is empty only when neither the subject (after reply prefixes such as "Re:", "Antw:", "AW:") nor the body has a letter or digit | Close is the one action no human sees again; a question written only in the subject must not be buried |
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
| Keywords miss typos ("refnud") | The model reads meaning and catches them; fuzzy matching would flood humans with false alarms | Test typo tickets in the eval and measure |
| Keywords can be dodged with invisible characters, look-alike letters or spaced-out words | Dodging them wins little: the agent cannot move money, and every reply must pass the FAQ checks | Strip invisible characters and map look-alike letters before matching |
| A card number split by line breaks or dots is not masked | Rare in real tickets | Widen the separators the masking accepts |
| The keyword lists were written after reading the 30 practice tickets and the 10 examples | Kept: the words are ordinary support vocabulary, and rewriting them now would change the agent just before the eval | The eval overstates keyword recall on unseen tickets; test the keywords on invented tickets written without looking at the lists |
| A crash between a successful post and its log line leaves the log one line short | The customer is unaffected: the helpdesk saved the answer and the ticket is off the open list | A start-up reconcile: record any handled ticket missing from the log |
| No parallel workers | Not needed for 30 tickets; the model's 4 to 8 seconds per ticket is the slow part | One fetcher handing each ticket to exactly one worker, with one shared pace limit under the helpdesk's 5 calls a second |
| Runner tests cover only the model-error paths (setup errors, start-up check, circuit breaker) | The rest is mostly glue, proven end to end by the crash test and dry runs | More tests with the same fake helpdesk and fake model (`tests/fakes.py`) |
| The same model writes the reply and checks it | Keeps one vendor and one setting; the check model is already a separate setting (`CHECK_MODEL`) | Measure how often the judge agrees with Nordavo's labels; try a stronger model for the judge only (Sonnet costs about 20x Haiku, still about 12 cents per 100 tickets for judging) |
| Back-translation uses the same model family as the drafter | Costs a hundredth of a cent per reply; a second vendor adds a key, a failure mode and another place customer text goes | Back-translate with a different engine (e.g. DeepL) for independence, log how often it disagrees with the drafter's English, and turn disagreements into eval cases |
