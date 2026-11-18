"""Every decision shape the agent can make goes through the real Helpdesk.send as a valid request.
The helpdesk is a fake transport; no network. Dry runs skip send(), so this is the post path's only check."""
import json

import httpx
import pytest

from agent.config import Config
from agent.decide import Proposal
from agent.helpdesk import Helpdesk
from agent.route import empty_decision, route
from agent.run import fallback_decision
from tests.fakes import TICKET

DOCUMENTED = {"language", "category", "priority", "reason", "draft_reply", "handoff_note", "confidence"}
P = Proposal(language="nl", category="question", priority="P4", priority_reason="How-to.", rule_flags=[],
             is_spam=False, faq_ids=["F02"], fully_covered=True, handoff_note="Customer asks how to add an employee.",
             draft_reply="Hoi, ga naar Team → Medewerker toevoegen. Team Roosterly", draft_english="Hi ...",
             confidence=0.9)  # invented

SHAPES = {
    "reply": route(P, set()),
    "rule handoff": route(P, {"refund"}),
    "other language": route(P.model_copy(update={"language": "other", "other_language": "French"}), set()),
    "not covered": route(P.model_copy(update={"fully_covered": False}), set()),
    "not covered, empty note": route(P.model_copy(update={"fully_covered": False, "handoff_note": ""}), set()),
    "unsure, empty note": route(P.model_copy(update={"confidence": 0.0, "handoff_note": ""}), set()),
    "fallback": fallback_decision(TICKET, "timeout"),
    "empty close": empty_decision(),
}


@pytest.mark.parametrize("name", SHAPES)
def test_every_decision_shape_posts_a_valid_request(name):
    sent = []
    transport = httpx.MockTransport(lambda request: sent.append(request) or httpx.Response(200, json={"ok": True}))
    hd = Helpdesk(Config("https://fake.test", "k", "me@example.com"), transport=transport, min_interval=0)
    d = SHAPES[name]
    assert hd.send("T900", d["action"], d) == "sent"
    body = json.loads(sent[0].content)
    assert sent[0].url.path.endswith(f"/tickets/T900/{d['action']}")
    assert set(body) <= DOCUMENTED and body["language"] in {"nl", "en", "de"}
