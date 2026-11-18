"""Code checks on reply drafts. Drafts are from a trial run on the examples (E-ids) or invented (marked)."""
import pytest

from agent import checks, decide, run
from agent.checks import code_checks
from tests.fakes import TICKET, FakeClient, parsed, runner, text_reply

CASES = [
    # (name, draft, customer language, ticket text, failing check or None)
    ("E01 Dutch reply to English ticket",
     "Hallo, de Roosterly-app werkt op iOS 16 en nieuwer en Android 10 en nieuwer. Uw iPhone 8 met iOS 15 "
     "voldoet daarom niet aan de eisen. Team Roosterly",
     "en", "The app crashes immediately on my iPhone 8 (iOS 15).", "language"),
    ("E07 price worked out from FAQ x ticket",
     "Hoi, Plus kost €6 per actieve medewerker per maand, excl. btw. Voor 25 medewerkers komt dat neer op €150 "
     "per maand excl. btw. Je kunt upgraden via Instellingen → Abonnement (Settings → Subscription). Team Roosterly",
     "nl", "Wat kost Plus voor 25 medewerkers?", None),
    ("E04 quoted label from the FAQ",
     "Je kunt een dienst ruilen door de dienst in de app te openen en op \"Ruil aanbieden\" te tikken. "
     "De manager keurt het goed onder Rooster → Verzoeken. Team Roosterly",
     "nl", "Hoe ruil ik een dienst met een collega?", None),
    ("invented: menu that does not exist",
     "Je vindt je facturen onder Instellingen → Betalingen. Team Roosterly",
     "nl", "Waar vind ik mijn facturen?", "labels"),
    ("T022 trial: German spelling of a Dutch menu name",
     "Jeder Nutzer kann seine Sprache selbst einstellen: unter Profil → Taal (Profil → Sprache). Team Roosterly",
     "de", "Gibt es die App auch auf Deutsch?", "labels"),
    ("invented: wrong last step in a menu chain",
     "Je vindt ze onder Instellingen → Abonnement → Rekeningen. Groet, Team Roosterly",
     "nl", "Waar vind ik mijn facturen?", "labels"),
    ("invented: German gloss in brackets is fine",
     "Hallo, jeder Nutzer wählt die Sprache unter Profiel → Taal (Profil → Sprache). Viele Grüße, Team Roosterly",
     "de", "Gibt es die App auch auf Deutsch?", None),
    ("invented: wrong number",
     "De resetlink is 30 minuten geldig. Ga naar app.roosterly.nl/login en klik op \"Wachtwoord vergeten\". "
     "Team Roosterly",
     "nl", "Wachtwoord vergeten", "numbers"),
    ("invented: made-up web address",
     "Je kunt stemmen op ideas.roosterly.nl. Wij lezen elk idee. Team Roosterly",
     "nl", "Donkere modus?", "urls"),
    ("invented: an FAQ web address written with https://",
     "Hoi, je kunt een nieuw wachtwoord aanvragen op https://app.roosterly.nl/login. Groet, Team Roosterly",
     "nl", "Wachtwoord vergeten", None),
    ("invented: an FAQ web address written with http:// at the end of a sentence",
     "Hoi, de status van de app zie je op http://status.roosterly.nl. Groet, Team Roosterly",
     "nl", "Werkt de app?", None),
    ("invented: a made-up web address with https:// is still caught",
     "Hoi, je kunt stemmen op https://ideas.roosterly.nl/vote. Groet, Team Roosterly",
     "nl", "Donkere modus?", "urls"),
    ("invented: card number in the draft",
     "We hebben je kaart 4111 1111 1111 1111 genoteerd. Dank je wel en groet, Team Roosterly",
     "nl", "Nieuwe kaart", "payment"),
    ("invented: apostrophes in English words are not quote marks",
     "Hi Sam, don't worry, you'll find your invoices under Instellingen → Abonnement → Facturen "
     "(Settings → Subscription → Invoices). Team Roosterly",
     "en", "Where are my invoices?", None),
    ("invented: apostrophes in Dutch words are not quote marks",
     "Hoi Anouk, de foto's van zo'n factuur vind je onder Instellingen → Abonnement → Facturen. Groet, Team Roosterly",
     "nl", "Waar vind ik mijn factuur?", None),
    ("invented: a made-up label in single quotes is still caught",
     "Hoi, tik op 'Dienst verwijderen' in de app. Groet, Team Roosterly",
     "nl", "Hoe verwijder ik een dienst?", "labels"),
    ("invented: a Dutch word-initial apostrophe ('s avonds) does not hide a made-up label",
     "Diensten die 's avonds beginnen vind je onder Rooster → Verzoeken. Tik op 'Dienst verwijderen'. Team Roosterly",
     "nl", "Waar vind ik mijn avonddiensten?", "labels"),
    ("invented: 's avonds next to a real label passes",
     "Diensten die 's avonds beginnen ruil je met 'Ruil aanbieden'. De manager keurt het goed onder Rooster → Verzoeken. "
     "Team Roosterly",
     "nl", "Hoe ruil ik een avonddienst?", None),
    ("invented: typographic apostrophes and quotes",
     "Hoi, geen zorgen: de foto’s staan er nog. Tik op ‘Dienst verwijderen’ in de app. Groet, Team Roosterly",
     "nl", "Hoe verwijder ik een dienst?", "labels"),
    ("invented: German reply",
     "Hallo, die App ist auf Deutsch verfügbar. Jeder Nutzer kann die Sprache unter Profiel → Taal "
     "(Profile → Language) wählen. Team Roosterly",
     "de", "Gibt es die App auch auf Deutsch?", None),
]


@pytest.mark.parametrize("name, draft, lang, ticket, failing", CASES, ids=[c[0] for c in CASES])
def test_code_checks(name, draft, lang, ticket, failing):
    results = code_checks(draft, lang, ticket)
    failed = {k for k, v in results.items() if v}
    if failing:
        assert failing in failed  # other checks may fail too (a card number is also an unknown number)
    else:
        assert failed == set()


# ---- the judge sees the customer's plan (fake model, no API calls)

PLAN_DRAFT = {"language": "nl", "faq_ids": ["F04"], "draft_english": "You can swap a shift ...",
              "draft_reply": "Je kunt een dienst ruilen door de dienst in de app te openen en op \"Ruil aanbieden\" "
                             "te tikken. De manager keurt het goed onder Rooster → Verzoeken. Team Roosterly"}


def judge(fits_plan):
    return checks.Verdict(supported_by_faq=True, answers_the_question=True, no_promises_beyond_faq=True,
                          matches_reading_aid=True, fits_customer_plan=fits_plan, problems=[])


def run_checks(monkeypatch, verdict, plan):
    client = FakeClient(create=[text_reply("You can swap a shift ...")], parse=[parsed(verdict)])
    monkeypatch.setattr(decide, "_client", client)
    passed, results, _ = checks.check_reply(PLAN_DRAFT, "Dienst ruilen\nHoe ruil ik een dienst?", plan)
    judge_message = client.requests[-1]["messages"][0]["content"]
    return passed, results, judge_message


def test_judge_sees_the_plan(monkeypatch):
    passed, _, message = run_checks(monkeypatch, judge(True), "Basis")
    assert passed and "<customer_plan>\nBasis\n</customer_plan>" in message


def test_claim_not_on_the_customers_plan_fails(monkeypatch):
    passed, results, _ = run_checks(monkeypatch, judge(False), "Basis")
    assert not passed and "fits_customer_plan" in results["model"]


def test_missing_plan_reaches_the_judge_as_unknown(monkeypatch, tmp_path):
    reply = decide.Proposal(language="nl", category="question", priority="P4", priority_reason="How-to.", rule_flags=[],
                            is_spam=False, faq_ids=PLAN_DRAFT["faq_ids"], fully_covered=True, handoff_note="Note.",
                            draft_reply=PLAN_DRAFT["draft_reply"], draft_english=PLAN_DRAFT["draft_english"],
                            confidence=0.9)
    client = FakeClient(create=["ok", text_reply("You can swap a shift ...")], parse=[parsed(reply), parsed(judge(True))])
    no_plan = {k: v for k, v in TICKET.items() if k != "customer_plan"}
    hd = runner(monkeypatch, tmp_path, client, [no_plan])
    assert run.main([]) == 0 and hd.posts == [("T900", "reply")]
    assert "<customer_plan>\nunknown\n</customer_plan>" in client.requests[-1]["messages"][0]["content"]
