"""Fakes for tests: an Anthropic client and a helpdesk. No network, no real tickets touched."""
from types import SimpleNamespace

import anthropic
import httpx2  # the SDK's own HTTP library; its errors carry these objects

_REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def status_error(cls, status):
    """A real SDK status error, e.g. status_error(anthropic.AuthenticationError, 401)."""
    return cls(f"fake {status}", response=httpx2.Response(status, request=_REQUEST), body=None)


def connection_error():
    return anthropic.APIConnectionError(request=_REQUEST)


def timeout_error():
    return anthropic.APITimeoutError(request=_REQUEST)


def parsed(proposal):
    """A successful messages.parse response carrying this proposal."""
    usage = SimpleNamespace(input_tokens=1, output_tokens=1)
    return SimpleNamespace(stop_reason="end_turn", parsed_output=proposal, usage=usage)


def text_reply(text):
    """A successful messages.create response with this text."""
    usage = SimpleNamespace(input_tokens=1, output_tokens=1)
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)], usage=usage)


class FakeClient:
    """Stands in for anthropic.Anthropic. Each call to messages.parse or messages.create takes
    the next item from its queue: an exception is raised, a callable is called, anything else is returned."""

    def __init__(self, parse=(), create=()):
        self.messages = self
        self._queues = {"parse": list(parse), "create": list(create)}
        self.calls = []
        self.requests = []  # the full keyword arguments of each call, for tests that read the prompt

    def _next(self, kind, kwargs):
        self.calls.append((kind, kwargs.get("model")))
        self.requests.append(kwargs)
        assert self._queues[kind], f"unexpected model call: {kind}"
        item = self._queues[kind].pop(0)
        if isinstance(item, BaseException):
            raise item
        return item() if callable(item) else item

    def parse(self, **kwargs):
        return self._next("parse", kwargs)

    def create(self, **kwargs):
        return self._next("create", kwargs)


class FakeHelpdesk:
    """Stands in for agent.helpdesk.Helpdesk in runner tests. Records every post."""

    def __init__(self, tickets):
        self.tickets = list(tickets)
        self.posts = []
        self.http_log = []

    def status(self):
        return {"mode": "practice", "open_tickets": len(self.tickets) - len(self.posts),
                "handled_tickets": len(self.posts)}

    def open_tickets(self):
        return iter(self.tickets)

    def get_ticket(self, ticket_id):
        return next(t for t in self.tickets if t["id"] == ticket_id)

    def send(self, ticket_id, action, decision):
        self.posts.append((ticket_id, action))
        return "sent"

    def close(self):
        pass


# ---- shared test setup

TICKET = {"id": "T900", "channel": "email", "customer_plan": "Basis", "subject": "Dienst ruilen",
          "body": "Hoe ruil ik een dienst met een collega?"}  # invented


def use(monkeypatch, client):
    """Replace decide.py's Anthropic client with a fake for this test."""
    from agent import decide
    monkeypatch.setattr(decide, "_client", client)


def runner(monkeypatch, tmp_path, client, tickets=None):
    """Point run.main at a fake helpdesk and a fake model. Returns the helpdesk."""
    from agent import run
    monkeypatch.chdir(tmp_path)  # the lock file and the log go here, not into the repo
    hd = FakeHelpdesk(tickets or [TICKET, {**TICKET, "id": "T901"}])
    monkeypatch.setattr(run, "Helpdesk", lambda cfg: hd)
    monkeypatch.setattr(run, "load_config", lambda: None)
    use(monkeypatch, client)
    return hd
