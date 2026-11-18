"""The eval's scoring and runner. Rows and examples are invented; no network, no model."""
import json

from agent.checks import Verdict
from agent.decide import Proposal
from eval import run_eval
from eval.score import action_miss, across_runs, score_row, totals
from tests.fakes import FakeClient, connection_error, parsed, text_reply, use

LABEL = {"language": "nl", "category": "question", "priority": "P4", "action": "reply", "reason": "FAQ F04."}


def decision(**overrides):
    return {"language": "nl", "category": "question", "priority": "P4", "action": "reply",
            "route_reason": "faq:F04", "flags": [], **overrides}


def test_row_scores_each_field_and_keeps_no_text():
    row = score_row("E99", LABEL, decision(priority="P3", reason="secret text", draft_reply="Hoi"),
                    {"model_calls": [{"in": 10, "out": 5, "cost_usd": 0.001}], "checks": {"labels": ["x"], "urls": []}})
    assert row["pass"] == {"language": True, "category": True, "priority": False, "action": True, "all": False}
    assert row["checks"] == ["labels"] and row["tokens_in"] == 10 and row["cost_usd"] == 0.001
    assert "secret text" not in json.dumps(row) and "Hoi" not in json.dumps(row) and "FAQ F04." not in json.dumps(row)


def test_model_failure_fails_every_field():
    row = score_row("E99", LABEL, None, error="model_failed: timeout")
    assert not any(row["pass"].values()) and action_miss(row) == "lost_work"


def test_action_misses_by_kind():
    handoff = {**LABEL, "action": "handoff"}
    assert action_miss(score_row("E1", handoff, decision(action="reply"))) == "unsafe"
    assert action_miss(score_row("E2", handoff, decision(action="close"))) == "unsafe"
    assert action_miss(score_row("E3", LABEL, decision(action="handoff"))) == "lost_work"
    assert action_miss(score_row("E6", LABEL, decision(action="close"))) == "unsafe"  # a buried question
    assert action_miss(score_row("E4", {**LABEL, "action": "close"}, decision(action="reply"))) == "other"
    assert action_miss(score_row("E5", LABEL, decision())) is None


def test_totals_count_replies_and_cost_per_100():
    rows = [score_row("E1", LABEL, decision(), {"model_calls": [{"in": 1, "out": 1, "cost_usd": 0.002}]}),
            score_row("E2", LABEL, decision(action="handoff")),
            score_row("E3", {**LABEL, "action": "handoff"}, decision(action="reply"))]
    t = totals(rows)
    assert (t["replies_labelled"], t["replies_made"], t["replies_right"]) == (2, 2, 1)
    assert (t["unsafe"], t["lost_work"], t["action"]) == (1, 1, 1)
    assert t["cost_per_100_usd"] == round(0.002 / 3 * 100, 4)


def test_across_runs_gives_ranges_and_flipped_ids():
    a = [score_row("E1", LABEL, decision()), score_row("E2", LABEL, decision())]
    b = [score_row("E1", LABEL, decision(action="handoff", route_reason="checks_failed:labels")),
         score_row("E2", LABEL, decision())]
    s = across_runs([{"totals": totals(a), "rows": a}, {"totals": totals(b), "rows": b}])
    assert s["ranges"]["action"] == (1, 2) and s["flipped"] == ["E1"]


def test_a_priority_moving_between_two_wrong_values_counts_as_flipped():
    a = [score_row("E1", LABEL, decision(priority="P3"))]
    b = [score_row("E1", LABEL, decision(priority="P2"))]
    assert across_runs([{"totals": totals(a), "rows": a}, {"totals": totals(b), "rows": b}])["flipped"] == ["E1"]


def test_judge_answers_are_names_in_four_states():
    def row(checks):
        return score_row("E1", LABEL, decision(), {"checks": checks})
    assert row(None)["judge_failed"] is None                                   # no draft was checked
    assert row({"labels": ["x"], "urls": []})["judge_failed"] is None          # a code check stopped it first
    assert row({"labels": [], "model": []})["judge_failed"] == []              # judged and passed
    r = row({"labels": [], "model": ["matches_reading_aid", "They differ: SECRET"]})
    assert r["judge_failed"] == ["matches_reading_aid"] and "SECRET" not in json.dumps(r)
    assert row({"model": ["judge failed (stop_reason=max_tokens)"]})["judge_failed"] == ["check_call_failed"]


def test_totals_count_judge_answers_with_their_denominator():
    rows = [score_row("E1", LABEL, decision(), {"checks": {"model": []}}),
            score_row("E2", LABEL, decision(), {"checks": {"model": ["matches_reading_aid", "note"]}}),
            score_row("E3", LABEL, decision(), {"checks": {"labels": ["y"]}}),
            score_row("E4", LABEL, decision(), {"checks": {"model": ["back-translation failed (stop_reason=x)"]}})]
    t = totals(rows)
    assert t["reached_judge"] == 2                       # a failed check call never got a verdict
    assert t["judge_failed"] == {"matches_reading_aid": 1, "check_call_failed": 1}


def test_dirty_flag_ignores_results_files_only():
    def fake_git(status):
        return lambda *args: "abc1234\n" if args[0] == "rev-parse" else status
    assert run_eval.git_state(fake_git("?? eval/results/eval-x.json\n")) == ("abc1234", False)
    assert run_eval.git_state(fake_git(" M agent/checks.py\n?? eval/results/eval-x.json\n")) == ("abc1234", True)


# ---- the runner: label removed, model failure recorded, setup error stops

EXAMPLE = {"id": "E99", "channel": "email", "customer_plan": "Basis", "subject": "Factuur",
           "body": "Waar vind ik mijn factuur?", "label": {**LABEL, "action": "handoff"}}  # invented
HANDOFF = Proposal(language="nl", category="question", priority="P4", priority_reason="How-to.", rule_flags=[],
                   is_spam=False, faq_ids=[], fully_covered=False, handoff_note="Customer asks for an invoice.",
                   draft_reply="", draft_english="", confidence=0.9)


class _Examples:
    def __init__(self, examples):
        self._examples = examples

    def examples(self):
        return self._examples

    def close(self):
        pass


def eval_main(monkeypatch, tmp_path, client, argv=()):
    monkeypatch.setattr(run_eval, "RESULTS", tmp_path)
    monkeypatch.setattr(run_eval, "load_config", lambda: None)
    monkeypatch.setattr(run_eval, "Helpdesk", lambda cfg: _Examples([EXAMPLE]))
    use(monkeypatch, client)
    code = run_eval.main(list(argv))
    return code, [json.loads(p.read_text(encoding="utf-8")) for p in sorted(tmp_path.glob("eval-*.json"))]


def test_eval_never_shows_the_label_and_writes_one_file_per_run(monkeypatch, tmp_path):
    seen, real = [], run_eval.decide_ticket
    monkeypatch.setattr(run_eval, "decide_ticket", lambda ticket: seen.append(ticket) or real(ticket))
    client = FakeClient(parse=[parsed(HANDOFF), parsed(HANDOFF)])
    code, results = eval_main(monkeypatch, tmp_path, client, ["--repeat", "2"])
    assert code == 0 and len(results) == 2
    assert len(seen) == 2 and all("label" not in t for t in seen)   # the agent is never handed the label
    row = results[0]["rows"][0]
    assert row["pass"]["all"] and results[0]["prompt_version"] and "git" in results[0]
    assert "Waar vind ik" not in json.dumps(results[0])


REPLY = HANDOFF.model_copy(update={  # invented: a draft that passes every code check, so it reaches the judge
    "faq_ids": ["F04"], "fully_covered": True, "draft_english": "You can swap a shift ...",
    "draft_reply": "Je kunt een dienst ruilen door de dienst in de app te openen en op \"Ruil aanbieden\" te tikken. "
                   "De manager keurt het goed onder Rooster → Verzoeken. Team Roosterly"})


def test_translations_file_holds_the_texts_and_the_scores_file_does_not(monkeypatch, tmp_path):
    verdict = Verdict(supported_by_faq=True, answers_the_question=True, no_promises_beyond_faq=True,
                      matches_reading_aid=False, fits_customer_plan=True, problems=["JUDGE-NOTE-SENTINEL"])
    client = FakeClient(create=[text_reply("BACK-TRANSLATION-SENTINEL")], parse=[parsed(REPLY), parsed(verdict)])
    code, results = eval_main(monkeypatch, tmp_path, client)
    assert code == 0 and "SENTINEL" not in json.dumps(results)
    assert results[0]["rows"][0]["judge_failed"] == ["matches_reading_aid"]
    (path,) = tmp_path.glob("translations-*.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["git"] == results[0]["git"] and saved["prompt_version"] == results[0]["prompt_version"]
    assert saved["entries"] == [{
        "id": "E99", "language": "nl", "draft_reply": REPLY.draft_reply, "draft_english": REPLY.draft_english,
        "back_translation": "BACK-TRANSLATION-SENTINEL", "judge_failed": ["matches_reading_aid"],
        "judge_notes": ["JUDGE-NOTE-SENTINEL"]}]


def test_show_leaves_the_judges_notes_to_the_translations_file(monkeypatch, tmp_path, capsys):
    # the notes repeat the back-translation; on screen they would spoil a blind review of the Dutch drafts
    verdict = Verdict(supported_by_faq=True, answers_the_question=True, no_promises_beyond_faq=True,
                      matches_reading_aid=False, fits_customer_plan=True, problems=["JUDGE-NOTE-SENTINEL"])
    client = FakeClient(create=[text_reply("BACK-TRANSLATION-SENTINEL")], parse=[parsed(REPLY), parsed(verdict)])
    eval_main(monkeypatch, tmp_path, client, ["--show"])
    assert "SENTINEL" not in capsys.readouterr().out


def test_no_translation_entry_without_a_back_translation(monkeypatch, tmp_path):
    code, _ = eval_main(monkeypatch, tmp_path, FakeClient(parse=[parsed(HANDOFF)]))
    (path,) = tmp_path.glob("translations-*.json")
    assert code == 0 and json.loads(path.read_text(encoding="utf-8"))["entries"] == []


def test_eval_records_a_model_failure_and_carries_on(monkeypatch, tmp_path):
    client = FakeClient(parse=[connection_error()] * 4)  # the SDK's own retries are inside the real client
    code, results = eval_main(monkeypatch, tmp_path, client)
    assert code == 0 and results[0]["rows"][0]["error"].startswith("model_failed")
    assert results[0]["totals"]["model_errors"] == 1
