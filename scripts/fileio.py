#!/usr/bin/env python3
"""Safe file writes and file locks, the same on Linux, macOS and Windows.

write_atomic: a full disk or a crash mid-write leaves the old file whole.
locked(f):    an exclusive lock on an open file (fcntl on Linux/macOS, msvcrt on Windows).
"""
import contextlib
import os
import sys
import tempfile
import time

# Goal files and messages hold "—", "·", "★", "⅔": print UTF-8 even where the console isn't
# (Windows defaults to cp1252 and would crash on them). Every script imports this module.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def write_atomic(path, text):
    """Write text to a temp file beside path, then rename it over path."""
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        else:
            os.chmod(tmp, 0o644)
        for attempt in range(20):  # Windows refuses to replace a file another process has open
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if os.name != "nt" or attempt == 19:
                    raise
                time.sleep(0.05)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


@contextlib.contextmanager
def locked(f):
    """Hold an exclusive lock for open file f until the with-block ends; other locked() callers
    on the same file wait. Linux/macOS lock f itself (advisory, readers unaffected). Windows
    locks are mandatory, so there a hidden sidecar `.<name>.lock` is locked instead and readers
    of f are never blocked."""
    if os.name == "nt":
        import msvcrt
        d, name = os.path.split(os.path.abspath(f.name))
        with open(os.path.join(d, f".{name}.lock"), "a+") as lk:
            lk.seek(0)
            while True:
                try:
                    msvcrt.locking(lk.fileno(), msvcrt.LK_LOCK, 1)
                    break
                except OSError:  # LK_LOCK gives up after ~10 s; keep waiting
                    continue
            try:
                yield f
            finally:
                f.flush()
                lk.seek(0)
                msvcrt.locking(lk.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield f
        finally:
            f.flush()
            fcntl.flock(f, fcntl.LOCK_UN)


@contextlib.contextmanager
def plan_lock(plan_path):
    """Serialise read-modify-write of a goal's plan.md (plan-set, the Stop hook's budget write):
    hold this for the whole read → edit → write_atomic, never just the write."""
    lock = os.path.join(os.path.dirname(os.path.abspath(plan_path)), ".plan.lock")
    with open(lock, "a") as f, locked(f):
        yield
