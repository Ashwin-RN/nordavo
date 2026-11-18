"""Code-only rules. No model is involved here, so none of this can be talked out of by a ticket.

1. mask()         removes payment details before any model call and before any log.
2. hard_rule_hits() finds the client's always-a-human topics by keyword, as a backstop to the model.
3. priority_floor() raises the priority for topics the brief says are urgent.
4. is_empty()     spots a ticket with nothing to answer.
5. screen()       runs 1 and 2 on a ticket: the normal path and the fallback both use it.

To add a hard rule or a keyword: add a line to HARD_RULES. Nothing else changes.
"""
import re
import unicodedata

# ---------------------------------------------------------------- hard rules
# Matched against lower-cased text with accents removed (beëindigen -> beeindigen).
# Keywords cover Dutch, English and German. The model's flags are the main check;
# these catch what the model misses.
# Each keyword is a stem. Where a stem also matched ordinary Dutch, that one reading is excluded
# ("klagen" is not "Klage"), so a stem never needs extra words to count: missing a refund costs more
# than a false alarm. tests/test_rules.py pins both sides with invented sentences.
HARD_RULES = {
    "refund": [
        r"terugbetal", r"terugstort", r"(?<!wachtwoord )terugkrijgen", r"geld terug", r"restitutie", r"creditnota",
        r"dubbel afgeschreven", r"twee keer .{0,20}afgeschreven", r"\brefund", r"charged twice",
        r"double charge", r"money back", r"ruckerstatt", r"(?<!bericht )erstatt", r"doppelt abgebucht",
    ],
    "cancellation": [
        # "opzeggen" splits in a sentence ("wij zeggen ons abonnement op."): the "op" must end the clause,
        # so "kunt u zeggen of het contract op tijd klaar is" does not match
        r"opzeg", r"opgezegd", r"\bzeg(gen)? (we|wij|ik) op\s*([.?!,]|$)",
        r"\bzeg(t|gen)?\b[^.?!\n]{0,40}\b(abonnement|contract|lidmaatschap)\b[^.?!\n]{0,25}\bop\s*([.?!,]|$)",
        r"beeindig", r"\bcancel", r"terminate", r"\b(ge)?kundig",
        r"betaalmethode", r"payment method", r"zahlungsmethode", r"downgrade",
    ],
    "gdpr": [
        r"\bavg\b", r"\bgdpr\b", r"\bdsgvo\b", r"persoonsgegevens", r"inzageverzoek",
        r"inzage in(?! (het|de|hun) (rooster|planning|uren|diensten))",
        r"gegevens .{0,30}verwijder", r"verwijder .{0,30}gegevens", r"personal data", r"delete my data",
        r"right to be forgotten", r"personenbezogene daten",
    ],
    "security": [
        r"gehackt?", r"\bhacked", r"datalek", r"data ?breach", r"phishing", r"onbevoegd(?! om\b)", r"unauthori[sz]ed",
        # "that wasn't us": the clause ends after "niet", so "in augustus waren wij niet open" does not match
        r"waren (wij|we) niet\s*([.?!,;:]|$)", r"dat was ik niet", r"wasn'?t us", r"niet door ons", r"vreemde login",
        r"suspicious login", r"account .{0,20}overgenomen",
    ],
    "legal": [  # a lawyer mentioned at all goes to a human (safety first)
        r"advocaat", r"jurist", r"rechtszaak", r"juridische stappen", r"schadevergoeding", r"aansprakelijk",
        r"\blawyer", r"attorney", r"legal action", r"\bsue\b", r"lawsuit", r"anwalt", r"\bklage(?!n\b)",
        r"verklag", r"aanklag", r"schadenersatz",
    ],
    "churn": [
        r"zeggen (we|wij) op\s*([.?!,]|$)", r"overstappen(?! naar (plus|basis)\b)", r"concurrent(?! (users?|gebruikers|sessions?)\b)",
        r"andere aanbieder", r"we('re| are)? (leaving|switching)", r"switch to another", r"wechseln zu",
    ],
    # Text addressed to an AI, or trying to change our instructions. Treated as a possible
    # security incident: handed off, and never allowed to set the priority.
    "injection": [
        r"negeer .{0,30}instructies", r"ignore .{0,30}instructions", r"ignoriere .{0,30}anweisungen",
        r"(?<!een )(?<!het )systeembericht", r"(?<!a )(?<!the )system ?message", r"system prompt",
        r"(voor|for|to) (de|the) ai\b", r"\b(beste|hallo|hoi|dear|hi|hello|hey) ai\b", r"(?<!een )(?<!an )ai[- ]assist",
        r"(you are|you're) now(?! (logged|signed)\b)", r"je bent nu(?! (ingelogd|uitgelogd|de beheerder)\b)",
    ],
}

# Security and legal risk are P1 in the brief. Money, contracts and personal data are at least P2.
# Injection has no floor on purpose: otherwise a ticket could raise its own priority by asking.
FLOORS = {"security": "P1", "legal": "P1",
          "refund": "P2", "cancellation": "P2", "gdpr": "P2", "churn": "P2", "payment_details": "P2"}

_COMPILED = {rule: [re.compile(p, re.MULTILINE) for p in pats] for rule, pats in HARD_RULES.items()}


def _normalise(text):
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def hard_rule_hits(text):
    """Set of hard-rule names whose keywords appear in the text."""
    t = _normalise(text)
    return {rule for rule, pats in _COMPILED.items() if any(p.search(t) for p in pats)}


def priority_floor(priority, flags):
    """Raise the priority to the floor any flag demands. Never lowers it."""
    for flag in flags:
        floor = FLOORS.get(flag)
        if floor and floor < priority:  # "P1" < "P2" as strings
            priority = floor
    return priority


_REPLY_PREFIX = re.compile(r"^\s*(?:(?:re|fwd?|antw|doorst|aw|wg)\s*:\s*)+", re.IGNORECASE)  # Re: FW: AW: ...


def is_empty(ticket):
    """Nothing to answer: no letter or digit in the subject (reply prefixes removed) or the body."""
    subject = _REPLY_PREFIX.sub("", ticket.get("subject") or "")
    return not re.search(r"\w", f"{subject} {ticket.get('body') or ''}")


# ---------------------------------------------------------------- masking
# Bias: over-mask. A wrongly masked number costs a human a second look;
# a leaked card number breaks a client rule.
_LONG_NUMBER = re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)")          # 13 to 19 digits
# An IBAN never starts on a Dutch VAT number (btw-nummer NL123456789B01): it is public, not a payment detail.
# A space after the country code ("NL 91 ABNA ...") only in capitals: "om 06 12345678" is a phone number.
_IBAN = re.compile(r"\b(?!NL\d{9}B\d{2}\b)(?:(?-i:[A-Z]{2}) |[A-Z]{2})\d{2}(?:[ ]?[A-Z0-9]){11,30}\b", re.IGNORECASE)
_NL_VAT = re.compile(r"NL\d{9}B\d{2}", re.IGNORECASE)                    # the same, written with spaces
_CVC = re.compile(r"\b(cvc|cvv|cvc2|cvv2|security code|beveiligingscode|prufziffer)\b\W{0,3}\d{3,4}", re.IGNORECASE)
_EXPIRY = re.compile(r"(?<!\d)(0[1-9]|1[0-2])\s?/\s?(\d{2}|20\d{2})(?!\d)")


def _luhn_ok(digits):
    total, double = 0, False
    for d in reversed(digits):
        n = int(d)
        if double:
            n = n * 2 - 9 if n > 4 else n * 2
        total, double = total + n, not double
    return total % 10 == 0


def _iban_ok(raw):
    s = raw.replace(" ", "").upper()
    s = s[4:] + s[:4]
    try:
        return int("".join(str(int(c, 36)) for c in s)) % 97 == 1
    except ValueError:
        return False


def mask(text):
    """Return (masked_text, kinds_found). kinds_found is e.g. {"card", "cvc", "expiry"}.

    Long digit runs are masked whether or not they pass the Luhn check: a mistyped card
    is still a card. Luhn and mod-97 only decide the label.
    """
    found = set()
    if not text:
        return text, found

    def iban(m):
        # The pattern lets a space join the next word ("NL91ABNA0417164300 overmaken"): give back trailing words
        # with no digit (they hide nothing), then judge what is left as if they were not there.
        raw = m.group()
        core = re.sub(r"(?: [A-Z]+)+$", "", raw, flags=re.IGNORECASE)
        compact = core.replace(" ", "")
        if _NL_VAT.fullmatch(compact):
            return raw  # a Dutch VAT number (btw-nummer) is public, not a payment detail
        if not re.search(r"\d{6,}", compact):
            return raw  # letters-and-few-digits: a word, not an account number
        found.add("iban" if _iban_ok(core) else "iban_like")
        return "[IBAN REMOVED]" + raw[len(core):]

    def card(m):
        digits = re.sub(r"\D", "", m.group())
        found.add("card" if _luhn_ok(digits) else "long_number")
        return "[CARD REMOVED]"

    text = _IBAN.sub(iban, text)
    text = _LONG_NUMBER.sub(card, text)

    def cvc(m):
        found.add("cvc")
        return f"{m.group(1)} [REMOVED]"

    text = _CVC.sub(cvc, text)
    if found & {"card", "long_number"}:
        def expiry(m):
            found.add("expiry")
            return "[EXPIRY REMOVED]"
        text = _EXPIRY.sub(expiry, text)
    return text, found


PAYMENT_KINDS = {"card", "long_number", "iban", "iban_like", "cvc"}


def screen(ticket):
    """Every code-only step before the model, in one place: used by the normal path and the fallback.
    Returns (masked subject, masked body, flags): keyword rules, plus "payment_details" if any were masked."""
    subject, k1 = mask(ticket.get("subject") or "")
    body, k2 = mask(ticket.get("body") or "")
    flags = hard_rule_hits(f"{subject}\n{body}")
    if (k1 | k2) & PAYMENT_KINDS:
        flags.add("payment_details")
    return subject, body, flags
