"""The planted-error rig. Fakes only: no network, no model."""
import json

from agent import decide
from agent.checks import Verdict
from eval import planted
from tests.fakes import FakeClient, parsed, text_reply

SPEC = {"examples": [{  # invented
    "example": "E99", "faq_ids": ["F03"], "english": "You can swap a shift in the app. Team Roosterly",
    "dutch": "Je kunt een dienst ruilen in de app. Team Roosterly",
    "planted": [{"id": "E99-negation", "kind": "negation", "old": "Je kunt", "new": "Je kunt niet",
                 "pattern": r"\bcannot\b"}]}]}


def verdict(ok):
    return Verdict(supported_by_faq=True, answers_the_question=True, no_promises_beyond_faq=True,
                   matches_reading_aid=ok, fits_customer_plan=True, problems=[] if ok else ["NOTE"])


def test_the_committed_variants_file_is_usable():
    spec = planted.load()
    assert planted.problems(spec) == []
    vs = list(planted.versions(spec))
    assert sum(v["kind"] == "control" for v in vs) == 4 and len(vs) == 20
    for v in vs:                                   # the Dutch changes, the English the reader sees never does
        ex = next(e for e in spec["examples"] if e["example"] == v["example"])
        assert v["english"] == ex["english"] and (v["dutch"] == ex["dutch"]) == (v["kind"] == "control")


def test_a_bad_variant_is_refused():
    bad = {"examples": [{**SPEC["examples"][0], "planted": [
        {"id": "x", "kind": "k", "old": "absent", "new": "y", "pattern": "a^"},
        {"id": "z", "kind": "k", "old": "Je kunt", "new": "Je kunt niet", "pattern": "swap"}]}]}
    assert len(planted.problems(bad)) == 2        # old text missing; pattern matches the honest English


def test_a_version_the_code_stops_makes_no_model_call(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(decide, "_client", client)
    v = {**next(planted.versions(SPEC)), "dutch": "Je kunt een dienst ruilen in de app, kijk op www.example.com. Team Roosterly"}
    row, usages = planted.check_version(v, "Dienst\nHoe ruil ik?", "Basis")
    assert row["code_failed"] == ["urls"] and client.requests == [] and usages == []
    assert planted.caught(row)


def test_layers_are_recorded_and_the_ticket_never_is(monkeypatch):
    client = FakeClient(create=[text_reply("You cannot swap a shift in the app.")], parse=[parsed(verdict(False))])
    monkeypatch.setattr(decide, "_client", client)
    v = list(planted.versions(SPEC))[1]
    row, _ = planted.check_version(v, "TICKET-SENTINEL\nHoe ruil ik?", "Basis")
    assert v["dutch"] == "Je kunt niet een dienst ruilen in de app. Team Roosterly"
    assert row["shown_in_back"] is True and row["judge_failed"] == ["matches_reading_aid"]
    assert row["judge_notes"] == ["NOTE"] and "TICKET-SENTINEL" not in json.dumps(row)


def test_a_control_records_patterns_that_fire_on_its_honest_reading(monkeypatch):
    client = FakeClient(create=[text_reply("You cannot miss it: swap in the app.")], parse=[parsed(verdict(True))])
    monkeypatch.setattr(decide, "_client", client)
    row, _ = planted.check_version(next(planted.versions(SPEC)), "Dienst\nHoe ruil ik?", "Basis")
    assert row["judge_failed"] == [] and row["control_pattern_hits"] == ["E99-negation"]
    assert not planted.caught(row)


def test_summary_counts_what_reached_the_customer():
    def row(kind, code=(), judge=None, shown=None):
        return {"kind": kind, "code_failed": list(code), "judge_failed": judge, "shown_in_back": shown,
                "control_pattern_hits": None, "error": None}
    s = planted.summary([row("negation", judge=[], shown=True), row("time", code=["numbers"]),
                         row("actor", judge=["supported_by_faq"], shown=False), row("control", judge=["x"])])
    assert (s["planted"], s["reached_customer"], s["stopped_by_code"], s["judged"]) == (3, 1, 1, 2)
    assert (s["held_by_judge"], s["shown_in_back"], s["control_false_alarms"]) == (1, 1, 1)
