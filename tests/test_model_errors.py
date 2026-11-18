"""How model errors are sorted: our setup is wrong (stop the run) or the model failed (this ticket only).
No API calls: decide.py's client is replaced by a fake."""
import anthropic
import pytest

from agent import checks, decide, run
from tests.fakes import FakeClient, FakeHelpdesk, connection_error, status_error, timeout_error

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

def runner(monkeypatch, tmp_path, client):
    """Point run.main at a fake helpdesk with two tickets and a fake model. Returns the helpdesk."""
    monkeypatch.chdir(tmp_path)  # the lock file and the log go here, not into the repo
    hd = FakeHelpdesk([TICKET, {**TICKET, "id": "T901"}])
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
