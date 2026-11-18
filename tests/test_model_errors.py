"""How model errors are sorted: our setup is wrong (stop the run) or the model failed (this ticket only).
No API calls: decide.py's client is replaced by a fake."""
import anthropic
import pytest

from agent import checks, decide, run
from tests.fakes import FakeClient, FakeHelpdesk, connection_error, parsed, status_error, timeout_error

TICKET = {"id": "T900", "channel": "email", "customer_plan": "Basis", "subject": "Dienst ruilen",
          "body": "Hoe ruil ik een dienst met een collega?"}  # invented

# A draft that passes every code check, so check_reply goes on to the model checks.
DECISION = {"language": "nl", "faq_ids": ["F04"], "draft_english": "You can swap a shift ...",
            "draft_reply": "Je kunt een dienst ruilen door de dienst in de app te openen en op \"Ruil aanbieden\" "
                           "te tikken. De manager keurt het goed onder Rooster → Verzoeken. Team Roosterly"}


def use(monkeypatch, client):
    monkeypatch.setattr(decide, "_client", client)


SETUP = [(anthropic.BadRequestError, 400), (anthropic.AuthenticationError, 401),
         (anthropic.PermissionDeniedError, 403), (anthropic.NotFoundError, 404)]
TRANSIENT = [(anthropic.RateLimitError, 429), (anthropic.InternalServerError, 500),
             (anthropic.OverloadedError, 529)]


@pytest.mark.parametrize("cls, status", SETUP)
def test_setup_errors_stop(monkeypatch, cls, status):
    use(monkeypatch, FakeClient(parse=[status_error(cls, status)]))
    with pytest.raises(decide.ModelSetupError):
        decide.propose(TICKET, TICKET["subject"], TICKET["body"])


@pytest.mark.parametrize("error", [status_error(c, s) for c, s in TRANSIENT] + [timeout_error(), connection_error()],
                         ids=lambda e: type(e).__name__)
def test_other_errors_fail_this_ticket(monkeypatch, error):
    use(monkeypatch, FakeClient(parse=[error]))
    with pytest.raises(decide.ModelFailed):
        decide.propose(TICKET, TICKET["subject"], TICKET["body"])


def test_cut_off_json_is_a_model_failure(monkeypatch):
    # The SDK checks the model's JSON with pydantic; cut-off output raises ValidationError, not an API error.
    use(monkeypatch, FakeClient(parse=[lambda: decide.Proposal.model_validate_json('{"language": "nl"')]))
    with pytest.raises(decide.ModelFailed):
        decide.propose(TICKET, TICKET["subject"], TICKET["body"])


@pytest.mark.parametrize("error", [connection_error(), status_error(anthropic.OverloadedError, 529)],
                         ids=lambda e: type(e).__name__)
def test_check_call_error_is_a_model_failure(monkeypatch, error):
    use(monkeypatch, FakeClient(create=[error]))  # the back-translation call fails
    with pytest.raises(decide.ModelFailed):
        checks.check_reply(DECISION, f"{TICKET['subject']}\n{TICKET['body']}")


# ---- the runner: the start-up call and a setup error mid-run

def runner(monkeypatch, tmp_path, client, tickets=None):
    """Point run.main at a fake helpdesk and a fake model. Returns the helpdesk."""
    monkeypatch.chdir(tmp_path)  # the lock file and the log go here, not into the repo
    hd = FakeHelpdesk(tickets or [TICKET, {**TICKET, "id": "T901"}])
    monkeypatch.setattr(run, "Helpdesk", lambda cfg: hd)
    monkeypatch.setattr(run, "load_config", lambda: None)
    use(monkeypatch, client)
    return hd


def test_bad_key_stops_at_start_up(monkeypatch, tmp_path):
    client = FakeClient(create=[status_error(anthropic.AuthenticationError, 401)])  # no triage call allowed
    hd = runner(monkeypatch, tmp_path, client)
    assert run.main([]) == 2
    assert hd.posts == [] and client.calls == [("create", decide.MODEL)]


def test_model_down_at_start_up_means_run_again(monkeypatch, tmp_path):
    hd = runner(monkeypatch, tmp_path, FakeClient(create=[status_error(anthropic.OverloadedError, 529)]))
    assert run.main([]) == 1
    assert hd.posts == []


def test_start_up_checks_each_model_once(monkeypatch, tmp_path):
    monkeypatch.setattr(decide, "CHECK_MODEL", "some-other-model")
    client = FakeClient(create=["ok", "ok"])
    runner(monkeypatch, tmp_path, client)
    decide.check_setup()
    assert client.calls == [("create", decide.MODEL), ("create", "some-other-model")]


def test_setup_error_mid_run_stops_with_nothing_posted(monkeypatch, tmp_path):
    hd = runner(monkeypatch, tmp_path, FakeClient(create=["ok"], parse=[status_error(anthropic.AuthenticationError, 401)]))
    assert run.main([]) == 2
    assert hd.posts == []  # no fallback handoff, nothing sent


# ---- the circuit breaker: MODEL_FAILURE_LIMIT model failures in a row stop the run

SPAM = decide.Proposal(language="nl", category="other", priority="P4", priority_reason="Advert.", rule_flags=[],
                       is_spam=True, faq_ids=[], fully_covered=False, handoff_note="Spam.", draft_reply="",
                       draft_english="", confidence=0.9)  # routes to close: no check calls needed


def tickets(*ids):
    return [{**TICKET, "id": i} for i in ids]


def down():
    return status_error(anthropic.OverloadedError, 529)


def test_three_failures_in_a_row_stop_with_no_fallback(monkeypatch, tmp_path):
    empty = {**TICKET, "id": "T0E", "subject": "", "body": ""}  # no model call: leaves the count alone
    client = FakeClient(create=["ok"], parse=[down(), down(), down()])
    hd = runner(monkeypatch, tmp_path, client, tickets("T01") + [empty] + tickets("T02", "T03", "T04"))
    assert run.main([]) == 1
    assert hd.posts == [("T0E", "close")]          # no fallback handoffs; T01 to T04 stay open
    assert [k for k, _ in client.calls].count("parse") == 3  # T04 was never tried


def test_a_success_resets_the_count(monkeypatch, tmp_path):
    # pass 1: fail, fail, ok, fail. pass 2: all three retried and fine. Never 3 in a row.
    client = FakeClient(create=["ok"], parse=[down(), down(), parsed(SPAM), down(),
                                              parsed(SPAM), parsed(SPAM), parsed(SPAM)])
    hd = runner(monkeypatch, tmp_path, client, tickets("T01", "T02", "T03", "T04"))
    assert run.main([]) == 0
    assert sorted(hd.posts) == [(i, "close") for i in ("T01", "T02", "T03", "T04")]


def test_count_carries_into_the_second_pass(monkeypatch, tmp_path):
    # pass 1: fail, ok, fail (count 1). pass 2: T01 fails again (2) -> fallback posted; T03 fails (3) -> stop.
    client = FakeClient(create=["ok"], parse=[down(), parsed(SPAM), down(), down(), down()])
    hd = runner(monkeypatch, tmp_path, client, tickets("T01", "T02", "T03"))
    assert run.main([]) == 1
    assert hd.posts == [("T02", "close"), ("T01", "handoff")]  # T03 tripped the breaker: nothing posted


# ---- re-checking one handled ticket (to see its draft again with --show)

def test_dry_run_rechecks_a_handled_ticket(monkeypatch, tmp_path):
    client = FakeClient(create=["ok"], parse=[parsed(SPAM)])
    hd = runner(monkeypatch, tmp_path, client, [{**TICKET, "handled": True}])
    assert run.main(["--dry-run", "--ticket", "T900"]) == 0
    assert [k for k, _ in client.calls] == ["create", "parse"] and hd.posts == []


def test_live_run_skips_a_handled_ticket(monkeypatch, tmp_path):
    client = FakeClient(create=["ok"])
    hd = runner(monkeypatch, tmp_path, client, [{**TICKET, "handled": True}])
    assert run.main(["--ticket", "T900"]) == 0
    assert [k for k, _ in client.calls] == ["create"] and hd.posts == []
