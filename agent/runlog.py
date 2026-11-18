"""One JSON line per ticket in logs/run-<timestamp>.jsonl.

Each line is written and flushed to disk before the next ticket starts, so a crash loses at most
the ticket in progress. The log never holds the ticket body, the draft text or payment details:
only the fields listed in ALLOWED.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ALLOWED = {
    "ticket_id", "action", "outcome", "language", "category", "priority", "confidence",
    "rule_flags", "faq_ids", "checks", "route_reason", "model_calls", "cost_usd",
    "latency_s", "http", "error", "dry_run", "prompt_version",
}


class RunLog:
    def __init__(self, directory="logs", **fixed):
        """fixed: fields stamped on every line of this run, e.g. prompt_version."""
        if set(fixed) - ALLOWED:  # checked here, before any ticket is touched
            raise ValueError(f"refusing to log fields {sorted(set(fixed) - ALLOWED)}")
        Path(directory).mkdir(exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = Path(directory) / f"run-{stamp}.jsonl"
        self.fixed = fixed
        self._f = open(self.path, "a", encoding="utf-8")

    def write(self, **fields):
        fields = {**self.fixed, **fields}
        unknown = set(fields) - ALLOWED
        if unknown:
            raise ValueError(f"refusing to log fields {sorted(unknown)}")
        line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
        self._f.write(json.dumps(line, ensure_ascii=False) + "\n")
        self._f.flush()
        os.fsync(self._f.fileno())

    def close(self):
        self._f.close()
