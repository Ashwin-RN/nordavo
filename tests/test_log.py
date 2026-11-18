"""The committed log holds the names of failed checks only: never the draft, its numbers or the judge's notes."""
import json
from pathlib import Path

from agent import decide, run
from tests.fakes import FakeClient, parsed
from tests.test_model_errors import TICKET, runner

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


def test_no_draft_checked_logs_null(monkeypatch, tmp_path):
    spam = CARD_DRAFT.model_copy(update={"is_spam": True, "fully_covered": False, "draft_reply": ""})
    runner(monkeypatch, tmp_path, FakeClient(create=["ok"], parse=[parsed(spam)]), [TICKET])
    run.main([])
    assert log_lines(tmp_path)[0]["checks"] is None
