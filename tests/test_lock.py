"""One run at a time: a live run's lock is respected, a crashed run's lock is taken over."""
import os
import subprocess
import sys

import pytest

from agent import lock


def test_a_live_runs_lock_stops_a_second_run(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    open(lock.LOCK, "w").write(str(os.getpid()))           # this test's own process: alive
    with pytest.raises(SystemExit):
        lock.take_lock()
    assert open(lock.LOCK).read() == str(os.getpid())       # the live run's lock is left alone


def test_a_crashed_runs_lock_is_taken_over(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    finished = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    open(lock.LOCK, "w").write(finished.stdout.strip())     # a process that has already exited
    lock.take_lock()
    assert open(lock.LOCK).read() == str(os.getpid())
    lock.release_lock()
    assert not os.path.exists(lock.LOCK)
