"""Client for the Roosterly helpdesk API.

What it guarantees (from api_reference.md):
- Both headers on every request.
- At most 4 requests a second (the limit is 5).
- 503: nothing was saved, so retry with backoff.
- 429: wait Retry-After seconds, then retry.
- 409: never retried. The customer already has an answer.
- 400, 401, 404, 422: our mistake. Raised at once, never looped.
- A network failure on a POST is ambiguous (it may have been saved).
  The client looks the ticket up before it sends again, so it never causes a 409.
"""
import random
import time

import httpx

from agent.config import Config

ACTIONS = ("reply", "handoff", "close")
COMMON_FIELDS = ("language", "category", "priority", "reason", "confidence")
ACTION_FIELDS = {"reply": ("draft_reply",), "handoff": ("handoff_note",), "close": ()}  # sent, and required


class HelpdeskError(Exception):
    """A response we must not retry. Carries the status and the API's error code."""

    def __init__(self, status, error, detail=None):
        self.status, self.error, self.detail = status, error, detail
        super().__init__(f"{status} {error}: {detail}" if detail else f"{status} {error}")


class AlreadyHandled(HelpdeskError):
    """409. The ticket has an answer already. Never retry."""


class Unavailable(HelpdeskError):
    """Retries ran out (503s, 429s or network failures). The ticket stays open for the next run."""


class Helpdesk:
    def __init__(self, cfg: Config, *, transport=None, max_attempts=6, min_interval=0.25,
                 timeout=20.0, sleep=time.sleep):
        self._client = httpx.Client(
            base_url=cfg.helpdesk_url,
            headers={"Authorization": f"Bearer {cfg.helpdesk_key}",
                     "X-Candidate-Email": cfg.candidate_email},
            timeout=timeout,
            transport=transport,
        )
        self.max_attempts = max_attempts
        self.min_interval = min_interval
        self._sleep = sleep
        self._last_call = 0.0
        self.http_log = []  # status codes seen, e.g. [503, 200]; the runner copies these into the log line

    # ---- low level -------------------------------------------------------

    def _throttle(self):
        wait = self._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last_call = time.monotonic()

    def _backoff(self, attempt):
        return min(8.0, 0.5 * 2 ** (attempt - 1)) + random.uniform(0, 0.25)

    def _request(self, method, path, *, json=None, params=None, retry_network=True):
        """Send one request, retrying only where the API says it is safe."""
        for attempt in range(1, self.max_attempts + 1):
            self._throttle()
            try:
                r = self._client.request(method, path, json=json, params=params)
            except httpx.TransportError as e:
                self.http_log.append("network")
                if not retry_network:
                    raise NetworkUncertain(str(e)) from e
                if attempt == self.max_attempts:
                    raise Unavailable(None, "network", str(e)) from e
                self._sleep(self._backoff(attempt))
                continue

            self.http_log.append(r.status_code)
            if r.status_code < 400:
                return r.json()

            body = _safe_json(r)
            error = body.get("error", "unknown")
            if r.status_code == 503:
                if attempt == self.max_attempts:
                    raise Unavailable(503, error, "retries exhausted")
                self._sleep(self._backoff(attempt))
                continue
            if r.status_code == 429:
                if attempt == self.max_attempts:
                    raise Unavailable(429, error, "retries exhausted")
                self._sleep(_retry_after(r))
                continue
            if r.status_code == 409:
                raise AlreadyHandled(409, error, body.get("message"))
            # 400, 401, 404, 422 and anything else: report and stop.
            raise HelpdeskError(r.status_code, error, body.get("problems") or body.get("message"))
        raise AssertionError("unreachable")

    # ---- endpoints -------------------------------------------------------

    def status(self):
        return self._request("GET", "/status")

    def examples(self):
        return self._request("GET", "/examples")["examples"]

    def get_ticket(self, ticket_id):
        return self._request("GET", f"/tickets/{ticket_id}")

    def open_tickets(self):
        """Every open ticket, following next_cursor until it is null."""
        cursor = None
        while True:
            params = {"limit": 10, "status": "open"}
            if cursor:
                params["cursor"] = cursor
            page = self._request("GET", "/tickets", params=params)
            yield from page["tickets"]
            cursor = page.get("next_cursor")
            if not cursor:
                return

    def send(self, ticket_id, action, decision):
        """Post one decision. Returns 'sent' or 'saved_before_timeout'.

        Only documented fields are sent. A missing field is caught here, before it becomes a 422.
        """
        if action not in ACTIONS:
            raise ValueError(f"unknown action {action!r}")
        body = {k: decision[k] for k in COMMON_FIELDS + ACTION_FIELDS[action] if decision.get(k) is not None}
        missing = [k for k in ("language", "category", "priority", "reason") + ACTION_FIELDS[action] if not body.get(k)]
        if missing:
            raise ValueError(f"{ticket_id}: missing {missing} for {action}")

        for _ in range(self.max_attempts):
            try:
                self._request("POST", f"/tickets/{ticket_id}/{action}", json=body, retry_network=False)
                return "sent"
            except NetworkUncertain:
                # It may have been saved. Look before sending again.
                if self.get_ticket(ticket_id).get("handled"):
                    return "saved_before_timeout"
                self._sleep(self._backoff(1))
        raise Unavailable(None, "network", f"{ticket_id}: could not confirm the {action}")

    def reset(self):
        return self._request("POST", "/practice/reset")

    def close(self):
        self._client.close()


class NetworkUncertain(Exception):
    """A POST failed in transit. We do not know whether it was saved."""


def _safe_json(r):
    try:
        data = r.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}


def _retry_after(r):
    try:
        return max(0.0, float(r.headers.get("Retry-After", "1")))
    except ValueError:
        return 1.0
