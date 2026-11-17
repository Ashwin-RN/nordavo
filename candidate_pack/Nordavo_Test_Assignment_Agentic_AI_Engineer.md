G R O N I N G E N   ×   B A N G A L O R E

Test assignment: Support ticket agent
Agentic AI Engineer · Take-home assignment · Deadline: 72 hours after our email

This is the second step in our process. You have 72 hours from the moment we send it: if it arrives on Monday, your delivery is
due on Thursday, end of day. The exact deadline is in our email. Keep it small. If something does not work yet, write down
what you left out; that is a useful answer in itself. We care more about your choices and how you explain them than about a
polished result. No user interface is needed.

0 1 T H E   S I T U A T I O N

Our client is a Dutch SaaS company. Its product, Roosterly, is a shift-planning app for restaurants and shops (the name is
fictional, the problem is real). Its support team of three receives about 200 tickets a week, almost all in Dutch. They want an
agent that answers what their help centre already covers and hands everything else to a human, ready to act on in under a
minute. A wrong answer reaches a real customer; escalating everything saves nobody time.

The tickets are in Dutch, on purpose. Everything else in this assignment is in English. You probably do not read Dutch.
In this role you build for Dutch clients whose customers write in Dutch, so working with a language you cannot read
yourself is part of the job, and part of this test.

0 2 W H A T   Y O U   G E T

What

What it is

Helpdesk API

The client's helpdesk, online. It holds 30 practice tickets and 10 example tickets labelled by us, with our
reasoning ( GET /examples ). The address and the key are in our email. Send the key and your own email
address with every request.

api_reference.md

Every endpoint, field and error, with curl examples.

faq.md

The client's help centre and their rules for the support team. Your agent may only answer from this file.

candidate_faq.md Answers to the questions candidates usually ask. Read it before you email us.

0 3 W H A T   T O   B U I L D

An agent that runs with one command, reads all open tickets from the helpdesk and posts one decision per ticket. Any
language, model or framework. For each ticket it decides the language, the category (bug, billing, feature_request, question,
other), the priority with a one-line reason, and one action:  reply  with a draft in the customer's language,  handoff  to a
human with a short note in English, or  close  for spam and empty tickets.

Priority

Definition

P1

P2

P3

P4

Many users blocked right now, or a security or legal risk.

One customer blocked, or money or the contract is involved.

Something is wrong or unclear, but there is a workaround.

No urgency: how-to questions, ideas, cosmetic issues.

It must behave like production code

It must work in Dutch

•

Handle the helpdesk's errors: random 503s, a 429 above 5
calls a second, a 409 when a ticket was already answered.

•

Replies go in the customer's language, so mostly Dutch.
Handoff notes are in English.

•

Safe to re-run: after a crash it continues where it stopped,
and no customer ever gets two answers.

•

One log line per ticket in  logs/ , without payment details.

•

How you handle the language is your choice: translate
first, work in Dutch directly, or something else. Each costs
something different.

•

Keys come from environment variables. Ticket text is
customer input: data, not instructions.

•

You must be able to check that a Dutch reply is correct
without reading Dutch yourself.

0 4 M E A S U R E   I T   A N D   F I X   O N E   T H I N G

•

Build an eval on the 10 labelled examples from  GET /examples . Do not let the model you are testing write labels.

Nordavo · Groningen × Bangalore · info@nordavo.nl

Take-home assignment · 1/2

G R O N I N G E N   ×   B A N G A L O R E

•

Find one thing your agent gets wrong, fix it, and show the eval result before and after.

POST /practice/reset  re-opens all practice tickets, so you can run as often as you like.

0 5 Y O U R   F I N A L   R U N ,   A N D   H O W   W E   C H E C K   I T

Before you send us your repo, do one clean run:  POST /practice/reset , then run your agent once over all 30 practice
tickets. That last run stays in the helpdesk. You do not send us any output.

•

We score your final run against our own labels: safety first, then whether FAQ questions get a good reply in the right
language, then category, priority and action.

•

We read your code as it was when your email arrived: how it calls the API, handles errors, decides to escalate, and works
in Dutch. Answers typed in by hand or copied into the code are easy to spot, and end the process.

•

The strongest candidates run their agent live in a 20-minute call, on new tickets they have not seen, sharing their
screen.

Sending an unsure ticket to a human is never punished; sending everything to a human is.

0 6 W H A T   T O   D E L I V E R

A GitHub repo (public, or private with access for  nordavo-hiring ) with your code, your eval, your logs and a
.env.example . Commit as you work; we read the history. A README of at most one page with these five headings:

Heading

How to run

Decisions

What goes in it

The commands, from a fresh clone.

Your three most important choices and why, including how you handled Dutch and how you used AI tools
to build it. Also what you assumed where the brief was unclear.

Reliability

How you handle 503, 429 and 409, what happens after a crash, and what you did about security.

Eval and fix

The eval result, the fix, the result after, and the cost per 100 tickets with the calculation.

What I would improve Your next step, and one thing in this brief or the client's rules you would change.

How to send it. After your final run, and before the deadline, reply to the email this brief came with. Subject:  Take-home:
<your full name> . One line, no attachments:  Repo:  the GitHub link. We grade the repo as it is when your email arrives.

0 7 Q U E S T I O N S ,   P R A C T I C A L   P O I N T S   A N D   H O W   W E   J U D G E

•

Open points: some things are left open on purpose, such as when your agent should count itself unsure. Ask us, or decide
and write it down under Decisions. Guessing silently is the only wrong answer. Reply to our email; we answer within one
working day.

•

Model and cost: any model, your own account. Free tiers and local models are fine; a paid model should cost well under
€1 for the whole assignment.

•

Your work stays yours. We do not use your code for any client. Everyone who submits gets written feedback.

•

Next step: if you pass, you book a 20-minute live session: your agent handles new tickets, you walk us through your code
and make one small change.

•

What we look at, in order: safe (the client's rules are followed, nothing harmful reaches a customer), useful (FAQ
questions get a good reply), robust, measured, and clearly explained. A small agent you fully understand beats a large one
you cannot explain.

Nordavo · Groningen × Bangalore · info@nordavo.nl

Take-home assignment · 2/2

