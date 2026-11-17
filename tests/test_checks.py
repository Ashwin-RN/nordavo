"""Code checks on reply drafts. Drafts are from a trial run on the examples (E-ids) or invented (marked)."""
import pytest

from agent.checks import code_checks

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
    ("invented: wrong number",
     "De resetlink is 30 minuten geldig. Ga naar app.roosterly.nl/login en klik op \"Wachtwoord vergeten\". "
     "Team Roosterly",
     "nl", "Wachtwoord vergeten", "numbers"),
    ("invented: made-up web address",
     "Je kunt stemmen op ideas.roosterly.nl. Wij lezen elk idee. Team Roosterly",
     "nl", "Donkere modus?", "urls"),
    ("invented: card number in the draft",
     "We hebben je kaart 4111 1111 1111 1111 genoteerd. Dank je wel en groet, Team Roosterly",
     "nl", "Nieuwe kaart", "payment"),
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
