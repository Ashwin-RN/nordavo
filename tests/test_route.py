"""Routing: code turns the model's proposal into the one action posted. Fake proposals, no API calls."""
from agent import route
from agent.decide import Proposal
from agent.rules import screen

CLEAN = Proposal(  # invented: a how-to the FAQ fully answers
    language="nl", category="question", priority="P4", priority_reason="How-to question.", rule_flags=[],
    is_spam=False, faq_ids=["F02"], fully_covered=True, handoff_note="Customer asks how to add an employee.",
    draft_reply="Hoi, ga naar Team → Medewerker toevoegen. Team Roosterly", draft_english="Hi, go to Team → Add employee.",
    confidence=0.9)


def proposal(**changes):
    return CLEAN.model_copy(update=changes)


def test_clean_covered_proposal_is_a_reply():
    d = route.route(CLEAN, set())
    assert d["action"] == "reply" and d["faq_ids"] == ["F02"] and d["priority"] == "P4"


def test_spam_with_a_flag_is_handed_off_not_closed():
    d = route.route(proposal(is_spam=True), {"legal"})
    assert d["action"] == "handoff" and d["route_reason"] == "rule:legal"


def test_unknown_faq_id_is_handed_off():
    d = route.route(proposal(faq_ids=["F99"]), set())
    assert d["action"] == "handoff" and "F99" in d["reason"]


def test_not_fully_covered_is_handed_off():
    assert route.route(proposal(fully_covered=False), set())["route_reason"] == "not_covered"


def test_low_confidence_is_handed_off():
    d = route.route(proposal(confidence=route.MIN_REPLY_CONFIDENCE - 0.01), set())  # follows the setting
    assert d["action"] == "handoff" and d["route_reason"] == "unsure"
    assert route.route(proposal(confidence=route.MIN_REPLY_CONFIDENCE), set())["action"] == "reply"  # at it: reply


def test_payment_details_are_handed_off_at_p2_at_least():
    subject, body, flags = screen({"subject": "Nieuwe kaart", "body": "Mijn kaart is 4111 1111 1111 1111."})
    d = route.route(CLEAN, flags)                       # even a clean, covered P4 proposal
    assert d["action"] == "handoff" and d["priority"] == "P2" and "payment_details" in d["flags"]
    assert "4111" not in body


def test_injection_does_not_raise_the_priority():
    d = route.route(proposal(rule_flags=["injection"]), set())
    assert d["action"] == "handoff" and d["priority"] == "P4"   # handed off, but no floor for injection
    # Code does not lower it either: the model's own reading of the ticket sets the priority.
    assert route.route(proposal(rule_flags=["injection"], priority="P1"), set())["priority"] == "P1"
