"""The fallback handoff (model failed twice) keeps the code-only rules: flags, priority floors, masking."""
from agent.run import fallback_decision


def test_hacked_gets_the_security_flag_and_p1():  # invented
    d = fallback_decision({"subject": "Help", "body": "We've been hacked, someone changed our rosters."}, "timeout")
    assert d["action"] == "handoff" and d["priority"] == "P1" and d["flags"] == ["security"]
    assert "security" in d["handoff_note"] and "security" in d["reason"]


def test_payment_details_floor_and_masking():  # invented
    d = fallback_decision({"subject": "Nieuwe kaart 4111 1111 1111 1111", "body": "Graag deze kaart gebruiken."}, "x")
    assert d["priority"] == "P2" and "payment_details" in d["flags"]
    assert "4111" not in str(d)


def test_no_rule_stays_p3():  # invented
    d = fallback_decision({"subject": "Vraag", "body": "Hoe werkt het rooster?"}, "x")
    assert d["priority"] == "P3" and d["flags"] == [] and d["category"] == "other"
