"""One run at a time: a lock file holding the run's process number.

A lock whose process is gone (a crashed run) is taken over. Asking the operating system whether the
process is alive needs no timer, so a slow but healthy run never loses its lock.
"""
import os
import sys

LOCK = ".run.lock"


def _pid_alive(pid):
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        k32.GetExitCodeProcess(handle, ctypes.byref(code))
        k32.CloseHandle(handle)
        return code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_lock():
    """Take the lock, or exit if another run holds it. A lock left by a crashed run is taken over."""
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                pid = int(open(LOCK).read().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _pid_alive(pid):
                sys.exit(f"Another run (pid {pid}) is active. Wait for it to finish.")
            print(f"Taking over a lock left by a crashed run (pid {pid}).")
            os.remove(LOCK)
    sys.exit(f"Could not take {LOCK}.")


def release_lock():
    os.remove(LOCK)
