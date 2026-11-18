"""The committed log holds the names of failed checks only: never the draft, its numbers or the judge's notes."""
import json
from pathlib import Path

from agent import checks, decide, run
from tests.fakes import TICKET, FakeClient, parsed, runner, text_reply

CARD_DRAFT = decide.Proposal(
    language="nl", category="billing", priority="P3", priority_reason="Card question.", rule_flags=[],
    is_spam=False, faq_ids=["F04"], fully_covered=True, handoff_note="Note.", confidence=0.9,
    draft_reply="We hebben je kaart 4111 1111 1111 1111 genoteerd. Dank je wel en groet, Team Roosterly",
    draft_english="We noted your card.")  # invented: a draft that repeats a card number


def log_lines(tmp_path):
    (path,) = Path(tmp_path, "logs").glob("run-*.jsonl")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_failed_draft_logs_check_names_only(monkeypatch, tmp_path):
    hd = runner(monkeypatch, tmp_path, FakeClient(create=["ok"], parse=[parsed(CARD_DRAFT)]), [TICKET])
    assert run.main([]) == 0
    assert hd.posts == [("T900", "handoff")]          # the checks held the draft back
    (line,) = log_lines(tmp_path)
    assert line["checks"] == ["numbers", "payment"]
    assert "4111" not in json.dumps(line) and "1111" not in json.dumps(line)


def test_the_back_translation_and_judge_notes_never_reach_the_log(monkeypatch, tmp_path):
    reply = CARD_DRAFT.model_copy(update={
        "category": "question", "draft_english": "You can swap a shift ...",
        "draft_reply": "Je kunt een dienst ruilen door de dienst in de app te openen en op \"Ruil aanbieden\" te "
                       "tikken. De manager keurt het goed onder Rooster → Verzoeken. Team Roosterly"})
    verdict = checks.Verdict(supported_by_faq=True, answers_the_question=True, no_promises_beyond_faq=True,
                             matches_reading_aid=False, fits_customer_plan=True, problems=["JUDGE-NOTE-SENTINEL"])
    client = FakeClient(create=["ok", text_reply("BACK-TRANSLATION-SENTINEL")], parse=[parsed(reply), parsed(verdict)])
    hd = runner(monkeypatch, tmp_path, client, [TICKET])
    assert run.main([]) == 0 and hd.posts == [("T900", "handoff")]
    (line,) = log_lines(tmp_path)
    assert line["checks"] == ["model"] and "SENTINEL" not in json.dumps(line)


def test_no_draft_checked_logs_null(monkeypatch, tmp_path):
    spam = CARD_DRAFT.model_copy(update={"is_spam": True, "fully_covered": False, "draft_reply": ""})
    runner(monkeypatch, tmp_path, FakeClient(create=["ok"], parse=[parsed(spam)]), [TICKET])
    run.main([])
    assert log_lines(tmp_path)[0]["checks"] is None


def test_every_line_carries_the_prompt_version(monkeypatch, tmp_path):
    runner(monkeypatch, tmp_path, FakeClient(create=["ok"], parse=[parsed(CARD_DRAFT)]), [TICKET])
    run.main([])
    (line,) = log_lines(tmp_path)
    assert line["prompt_version"] == run.prompt_version() and len(line["prompt_version"]) == 8


def test_prompt_version_changes_with_anything_sent_to_the_model(monkeypatch):
    from agent import checks
    before = run.prompt_version()
    for module, name in [(checks, "JUDGE_SYSTEM"), (checks, "BACK_TRANSLATE_SYSTEM"), (decide, "SYSTEM"),
                         (decide, "MODEL"), (decide, "CHECK_MODEL"), (decide, "EFFORT"),
                         (checks, "BACK_TRANSLATE_EFFORT"), (checks, "JUDGE_EFFORT")]:
        with monkeypatch.context() as m:
            m.setattr(module, name, getattr(module, name) + " changed")
            assert run.prompt_version() != before, name
    assert run.prompt_version() == before  # and back again once the change is undone
    for module, name, other in [(decide, "Proposal", "Verdict"), (checks, "Verdict", "Proposal")]:  # the two forms
        with monkeypatch.context() as m:
            m.setattr(module, name, getattr(checks if other == "Verdict" else decide, other))
            assert run.prompt_version() != before, name


def test_an_unknown_fixed_field_stops_before_any_line(tmp_path):
    import pytest
    from agent.runlog import RunLog
    with pytest.raises(ValueError):
        RunLog(tmp_path, ticket_text="never")


def test_a_run_that_logs_nothing_leaves_no_file(tmp_path):
    from agent.runlog import RunLog
    empty, used = RunLog(tmp_path / "a"), RunLog(tmp_path / "b")
    used.write(ticket_id="T900")
    empty.close(), used.close()
    assert not empty.path.exists() and used.path.exists()
