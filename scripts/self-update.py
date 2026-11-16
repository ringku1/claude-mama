#!/usr/bin/env python3
"""Keep a one-line (git) install of mama current. The hooks start it in the background at most
once a day (hooks/mama-hook.py → maybe_self_update); it never prints and never blocks a session.

Usage: self-update.py [<skill folder>]   # default: the folder this script is in

Does nothing unless the folder is mama's own git checkout (not a plugin copy, not a worktree), on
`main` with an upstream, with no local changes, and MAMA_AUTO_UPDATE isn't 0. Then it fetches,
fast-forwards to the upstream, and — when that brought new commits — re-runs install.py so the
hook registration follows the release. Errors go to ~/.claude/mama/hook-errors.log.
"""
import datetime
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
ERRORS = os.path.expanduser("~/.claude/mama/hook-errors.log")
ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0")  # never wait on a credentials prompt


def git(root, *args):
    r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60, env=ENV)
    return r.stdout.strip() if r.returncode == 0 else None


def update(root):
    """True when new commits were fast-forwarded in; False when there was nothing to do or it was skipped."""
    if os.environ.get("MAMA_AUTO_UPDATE", "1") == "0" or not os.path.isdir(os.path.join(root, ".git")):
        return False
    if git(root, "symbolic-ref", "--short", "HEAD") != "main" or git(root, "rev-parse", "--abbrev-ref", "@{upstream}") is None:
        return False
    if git(root, "status", "--porcelain") != "":
        return False  # local changes: the user's to sort out (the installer says how)
    before = git(root, "rev-parse", "HEAD")
    if git(root, "fetch", "-q") is None or git(root, "merge", "-q", "--ff-only", "@{upstream}") is None:
        return False
    return git(root, "rev-parse", "HEAD") != before


def main():
    root = os.path.realpath(sys.argv[1]) if len(sys.argv) > 1 else ROOT
    try:
        if update(root) and os.path.exists(os.path.join(root, "install.py")):
            subprocess.run([sys.executable, os.path.join(root, "install.py")], capture_output=True, timeout=120)
    except Exception as e:  # noqa: BLE001 — a background updater must never surface
        try:
            os.makedirs(os.path.dirname(ERRORS), exist_ok=True)
            with open(ERRORS, "a", encoding="utf-8") as f:
                f.write(f"{datetime.datetime.now():%Y-%m-%d %H:%M} self-update {type(e).__name__}: {e}\n")
        except OSError:
            pass


if __name__ == "__main__":
    main()
