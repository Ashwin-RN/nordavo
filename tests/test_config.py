"""Settings: a fresh clone fails fast with a clear message, and a blank line in .env means the default."""
import os

import pytest

from agent import config, lock, run

ALL = {"HELPDESK_URL": "https://fake.test", "HELPDESK_KEY": "k", "CANDIDATE_EMAIL": "me@example.com",
       "ANTHROPIC_API_KEY": "fake-key"}


@pytest.fixture
def env(monkeypatch):
    for name, value in ALL.items():  # set every variable here, so the real .env never decides a test
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_missing_anthropic_key_is_one_clear_line(env, capsys):
    env.delenv("ANTHROPIC_API_KEY")
    with pytest.raises(SystemExit) as stop:
        config.load_config()
    assert stop.value.code == 2                    # a setup problem: fix the cause, don't just run again
    message = capsys.readouterr().err
    assert "ANTHROPIC_API_KEY" in message and message.count("\n") == 1


def test_all_set_loads(env):
    assert config.load_config().helpdesk_url == "https://fake.test"


@pytest.mark.parametrize("value, expected", [(None, "default"), ("", "default"), ("set", "set")])
def test_blank_setting_means_default(env, value, expected):
    if value is None:
        env.delenv("SOME_SETTING", raising=False)
    else:
        env.setenv("SOME_SETTING", value)
    assert config.setting("SOME_SETTING", "default") == expected


def test_missing_config_leaves_no_lock(env, tmp_path):
    env.chdir(tmp_path)
    env.delenv("ANTHROPIC_API_KEY")
    env.setattr(run, "Helpdesk", lambda cfg: pytest.fail("reached the helpdesk"))
    with pytest.raises(SystemExit):
        run.main([])
    assert not os.path.exists(lock.LOCK)
