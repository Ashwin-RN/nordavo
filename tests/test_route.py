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


def test_unsure_spam_is_handed_off_not_closed():  # close is the one action no human sees again
    d = route.route(proposal(is_spam=True, confidence=route.MIN_REPLY_CONFIDENCE - 0.01), set())
    assert d["action"] == "handoff" and d["route_reason"] == "unsure_spam" and d["handoff_note"]
    assert route.route(proposal(is_spam=True, confidence=route.MIN_REPLY_CONFIDENCE), set())["action"] == "close"


def test_unknown_faq_id_is_handed_off():
    d = route.route(proposal(faq_ids=["F99"]), set())
    assert d["action"] == "handoff" and "F99" in d["reason"]


def test_not_fully_covered_is_handed_off():
    assert route.route(proposal(fully_covered=False), set())["route_reason"] == "not_covered"


def test_a_draft_without_an_english_version_is_handed_off():  # the judge compares the two; nothing to compare
    for empty in ("", "  \n"):
        d = route.route(proposal(draft_english=empty), set())
        assert d["action"] == "handoff" and d["route_reason"] == "no_english" and d["handoff_note"]


def test_an_english_draft_is_its_own_english_version():  # no second copy needed, and no needless handoff
    draft = "Hi, go to Team → Medewerker toevoegen (Add employee). Team Roosterly"
    for empty in ("", "  \n"):
        d = route.route(proposal(language="en", draft_reply=draft, draft_english=empty), set())
        assert d["action"] == "reply" and d["draft_english"] == draft
    assert route.route(CLEAN, set())["draft_english"] == CLEAN.draft_english  # a given English version is kept


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


# ---- languages we don't reply in (Fix J)

FRENCH = dict(language="other", other_language="French")


def test_other_language_is_handed_off_in_en_and_named():
    d = route.route(proposal(**FRENCH), set())          # even a covered draft with high confidence
    assert d["action"] == "handoff" and d["language"] == "en" and d["route_reason"] == "language:other"
    assert d["handoff_note"].startswith("Customer wrote in French")


def test_other_language_spam_still_closes():
    d = route.route(proposal(is_spam=True, **FRENCH), set())
    assert d["action"] == "close" and d["language"] == "en"


def test_other_language_with_a_rule_keeps_the_rule_and_names_the_language():
    d = route.route(proposal(**FRENCH), {"refund"})
    assert d["route_reason"] == "rule:refund" and d["language"] == "en" and "French" in d["handoff_note"]


def test_other_is_a_value_the_form_accepts():  # built through validation, so removing "other" from the form fails here
    p = Proposal.model_validate({**CLEAN.model_dump(), **FRENCH})
    assert route.route(p, set())["language"] == "en"


def test_unnamed_other_language_still_explains_itself():
    note = route.route(proposal(language="other", other_language=""), set())["handoff_note"]
    assert note.startswith("Customer wrote in a language we do not reply in")


def test_a_new_hard_rule_needs_only_its_keywords():  # rules.py: "add a line to HARD_RULES. Nothing else changes."
    d = route.route(CLEAN, {"pricing_dispute"})        # a flag with no wording in RULE_TEXT yet
    assert d["action"] == "handoff" and "pricing dispute" in d["reason"] and "pricing dispute" in d["handoff_note"]
