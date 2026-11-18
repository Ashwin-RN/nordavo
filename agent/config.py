"""Settings come from environment variables (or a local .env). Nothing secret lives in the code.

Importing this module loads .env once; a variable already set in the environment wins over .env.
"""
import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

REQUIRED = ("HELPDESK_URL", "HELPDESK_KEY", "CANDIDATE_EMAIL", "ANTHROPIC_API_KEY")


@dataclass(frozen=True)
class Config:
    helpdesk_url: str
    helpdesk_key: str
    candidate_email: str


def setting(name, default):
    """An optional setting. A blank line in .env (NAME=) means the default, not an empty value."""
    return os.environ.get(name) or default


def load_config() -> Config:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}. Copy .env.example to .env and fill it in.",
              file=sys.stderr)
        raise SystemExit(2)  # exit 2: fix the cause first (exit 1 would mean "run again later")
    return Config(
        helpdesk_url=os.environ["HELPDESK_URL"].rstrip("/"),
        helpdesk_key=os.environ["HELPDESK_KEY"],
        candidate_email=os.environ["CANDIDATE_EMAIL"],
    )
