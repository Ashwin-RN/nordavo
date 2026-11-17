"""The helpdesk client against a fake server. No network, no real tickets touched."""
import httpx
import pytest

from agent.config import Config
from agent.helpdesk import AlreadyHandled, Helpdesk, HelpdeskError, Unavailable

CFG = Config("https://fake.test/helpdesk", "test-key", "me@example.com")
DECISION = {"language": "nl", "category": "question", "priority": "P4",
            "reason": "FAQ F01.", "draft_reply": "Hoi ...", "handoff_note": "should not be sent"}


def client(responses, seen):
    """A Helpdesk whose server replays `responses` in order and records every request."""
    queue = list(responses)

    def handler(request):
        seen.append(request)
        nxt = queue.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    return Helpdesk(CFG, transport=httpx.MockTransport(handler), min_interval=0, sleep=lambda s: None)


def test_both_headers_on_every_request():
    seen = []
    client([httpx.Response(200, json={"mode": "practice"})], seen).status()
    assert seen[0].headers["Authorization"] == "Bearer test-key"
    assert seen[0].headers["X-Candidate-Email"] == "me@example.com"


def test_503_is_retried_then_succeeds():
    seen = []
    hd = client([httpx.Response(503, json={"error": "service_unavailable"}),
                 httpx.Response(200, json={"ok": True})], seen)
    assert hd.send("T001", "reply", DECISION) == "sent"
    assert len(seen) == 2
    assert hd.http_log == [503, 200]


def test_429_waits_retry_after():
    seen, waits = [], []
    hd = client([httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "rate_limited"}),
                 httpx.Response(200, json={"mode": "practice"})], seen)
    hd._sleep = waits.append
    hd.status()
    assert 2.0 in waits


def test_409_is_never_retried():
    seen = []
    hd = client([httpx.Response(409, json={"error": "already_handled"})], seen)
    with pytest.raises(AlreadyHandled):
        hd.send("T001", "reply", DECISION)
    assert len(seen) == 1


@pytest.mark.parametrize("code", [400, 401, 404, 422])
def test_our_mistakes_stop_at_once(code):
    seen = []
    hd = client([httpx.Response(code, json={"error": "x", "problems": ["priority"]})], seen)
    with pytest.raises(HelpdeskError) as e:
        hd.send("T001", "reply", DECISION)
    assert e.value.status == code
    assert len(seen) == 1


def test_503_forever_gives_up():
    seen = []
    hd = client([httpx.Response(503, json={"error": "service_unavailable"})] * 6, seen)
    with pytest.raises(Unavailable):
        hd.send("T001", "reply", DECISION)
    assert len(seen) == 6


def test_timeout_then_already_saved_does_not_send_again():
    seen = []
    hd = client([httpx.ReadTimeout("slow"),
                 httpx.Response(200, json={"id": "T001", "handled": {"action": "reply"}})], seen)
    assert hd.send("T001", "reply", DECISION) == "saved_before_timeout"
    assert [r.method for r in seen] == ["POST", "GET"]


def test_timeout_then_not_saved_sends_again():
    seen = []
    hd = client([httpx.ReadTimeout("slow"),
                 httpx.Response(200, json={"id": "T001", "handled": None}),
                 httpx.Response(200, json={"ok": True})], seen)
    assert hd.send("T001", "reply", DECISION) == "sent"
    assert [r.method for r in seen] == ["POST", "GET", "POST"]


def test_only_documented_fields_are_sent():
    seen = []
    client([httpx.Response(200, json={"ok": True})], seen).send("T001", "reply", DECISION)
    sent = httpx.Response(200, content=seen[0].content).json()
    assert "handoff_note" not in sent
    assert set(sent) == {"language", "category", "priority", "reason", "draft_reply"}


def test_missing_field_caught_before_sending():
    seen = []
    hd = client([], seen)
    with pytest.raises(ValueError):
        hd.send("T001", "handoff", {"language": "nl", "category": "billing", "priority": "P2", "reason": "x"})
    assert seen == []


def test_pagination_follows_cursor_to_null():
    seen = []
    hd = client([httpx.Response(200, json={"tickets": [{"id": "T001"}], "next_cursor": "T001"}),
                 httpx.Response(200, json={"tickets": [{"id": "T002"}], "next_cursor": None})], seen)
    assert [t["id"] for t in hd.open_tickets()] == ["T001", "T002"]
    assert seen[1].url.params["cursor"] == "T001"
