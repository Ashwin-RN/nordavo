"""Code turns the model's proposal into the one decision that is posted.

First match wins:
  1. empty ticket                          -> close   (decided by code, no model call)
  2. model says spam, and no rule flag      -> close if confidence >= MIN_REPLY_CONFIDENCE, else handoff
  3. any rule flag (model or keyword) or payment details -> handoff
  4. written in a language we don't reply in ("other")  -> handoff, posted as "en", the note names it
  5. no FAQ id, unknown FAQ id, or not fully covered     -> handoff
  6. a Dutch or German draft with no English version (nothing for the judge to compare) -> handoff;
     an English draft is its own English version
  7. model confidence below MIN_REPLY_CONFIDENCE          -> handoff
  8. otherwise                           -> reply candidate (checks.py checks it before it is sent)
"""
from agent.config import setting
from agent.decide import FAQ_IDS
from agent.rules import priority_floor

# Below this self-reported confidence a reply goes to a human instead. The model's confidence is a
# weak signal on its own, so it is one gate among several, not the main one.
MIN_REPLY_CONFIDENCE = float(setting("MIN_REPLY_CONFIDENCE", "0.7"))


RULE_TEXT = {
    "refund": "refund or disputed charge",
    "cancellation": "cancellation or contract change",
    "gdpr": "personal data request (GDPR/AVG)",
    "security": "possible security incident",
    "legal": "legal threat",
    "churn": "customer threatens to leave",
    "injection": "ticket contains instructions aimed at the AI (possible security incident)",
    "payment_details": "customer sent payment details",
}


def empty_decision():
    return {
        "action": "close", "language": "nl", "category": "other", "priority": "P4",
        "reason": "Empty ticket: no subject content or body to act on. Closed without action.",
        "route_reason": "empty", "flags": [],
    }


def route(proposal, code_flags):
    """Return the decision dict to post (action plus API fields) and why. code_flags come from rules.screen()."""
    flags = set(proposal.rule_flags) | set(code_flags)
    priority = priority_floor(proposal.priority, flags)
    other = proposal.language == "other"            # the API takes only nl, en, de: post "en", name it in the note
    language_name = proposal.other_language.strip() or "a language we do not reply in"
    model_note = proposal.handoff_note.strip() or "The agent wrote no note: please read the ticket."  # never empty
    note = (f"Customer wrote in {language_name}; we reply only in nl, en, de.\n" if other else "") + model_note
    base = {"language": "en" if other else proposal.language, "category": proposal.category, "priority": priority,
            "confidence": round(max(0.0, min(1.0, proposal.confidence)), 2), "flags": sorted(flags)}

    if proposal.is_spam and not flags:
        if proposal.confidence >= MIN_REPLY_CONFIDENCE:  # close is never seen again: it needs the reply's bar
            return {**base, "action": "close", "route_reason": "spam",
                    "reason": f"{proposal.priority_reason} Spam or unrelated to Roosterly: closed."}
        return {**base, "action": "handoff", "route_reason": "unsure_spam", "handoff_note": note,
                "reason": f"{proposal.priority_reason} Looks like spam, but the agent was unsure: a human checks it."}

    if flags:
        return {**base, "action": "handoff", "route_reason": "rule:" + ",".join(sorted(flags)),
                "reason": f"{proposal.priority_reason} Client rule, a human handles it: {rule_text(flags)}.",
                "handoff_note": rule_note(note, flags)}

    if other:
        return {**base, "action": "handoff", "route_reason": "language:other", "handoff_note": note,
                "reason": f"{proposal.priority_reason} Handed to a human: written in {language_name}, "
                          f"a language we do not reply in."}

    faq_ids = [f.upper() for f in proposal.faq_ids]
    unknown = [f for f in faq_ids if f not in FAQ_IDS]
    if not faq_ids or unknown or not proposal.fully_covered or not proposal.draft_reply.strip():
        why = "the FAQ does not fully answer it" if not unknown else f"cited unknown FAQ ids {unknown}"
        return {**base, "action": "handoff", "route_reason": "not_covered",
                "reason": f"{proposal.priority_reason} Handed to a human: {why}.",
                "handoff_note": note}

    # The judge compares the draft with its English version. An English draft is its own English version;
    # a Dutch or German draft without one cannot be compared, so a human checks it.
    english = proposal.draft_english if proposal.draft_english.strip() else (
        proposal.draft_reply if proposal.language == "en" else "")
    if not english:
        return {**base, "action": "handoff", "route_reason": "no_english",
                "reason": f"{proposal.priority_reason} Handed to a human: the draft has no English version to "
                          f"check it against.",
                "handoff_note": note}

    if proposal.confidence < MIN_REPLY_CONFIDENCE:
        return {**base, "action": "handoff", "route_reason": "unsure",
                "reason": f"{proposal.priority_reason} Handed to a human: the agent was unsure of its answer.",
                "handoff_note": note}

    return {**base, "action": "reply", "route_reason": "faq:" + ",".join(faq_ids), "faq_ids": faq_ids,
            "reason": f"{proposal.priority_reason} Answered from FAQ {', '.join(faq_ids)}.",
            "draft_reply": proposal.draft_reply, "draft_english": english,
            "handoff_note": note}


def rule_text(flags):
    """The client rules that apply, in words, e.g. "legal threat; refund or disputed charge".
    A rule with no wording in RULE_TEXT yet is described by its own name, so a new hard rule never stops the run."""
    return "; ".join(RULE_TEXT.get(f, f.replace("_", " ")) for f in sorted(flags))


def rule_note(note, flags):
    """The handoff note, headed by the client rules that apply, if any."""
    return f"Rule: {rule_text(flags)}.\n{note}".strip() if flags else note
