#!/usr/bin/env python3
"""Wait for the CI runs on a pushed commit and report them — a goal is met only when its CI is green.

Usage: ci-wait.py <repo dir> <sha> [--log <log.md>] [--timeout <minutes>]
  ci-wait.py <worktree> 1a2b3c4 --log <store>/<slug>/log.md     # run it in the background
Asks GitHub (`gh run list --commit`) until every run on <sha> has finished, then prints one line and,
with --log, appends it to the goal's log through log.py:
  ci <sha>: green — 3 runs                                          exit 0
  ci <sha>: red — test (failure) <url>; …                           exit 1
  ci <sha>: pending — 2 of 3 runs still running after <m>m          exit 3
  ci none: <why> (no gh, not signed in, no run started for <sha>)   exit 0
MAMA_CI_POLL (seconds between asks, default 15) and MAMA_CI_APPEAR (seconds to wait for a first run,
default 120) are for tests.
"""
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS = {"success", "skipped", "neutral"}


def runs(repo, sha):
    """The workflow runs on <sha>, newest first per workflow (a re-run replaces the old result);
    or a string saying why GitHub couldn't be asked."""
    gh = shutil.which("gh")
    if not gh:
        return "gh not installed"
    try:
        r = subprocess.run([gh, "run", "list", "--commit", sha, "-L", "50", "--json",
                            "databaseId,workflowName,status,conclusion,url,createdAt"],
                           cwd=repo, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return f"gh failed: {e}"
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip().splitlines()
        return f"gh: {msg[0] if msg else 'exit ' + str(r.returncode)}"
    try:
        found = json.loads(r.stdout or "[]")
    except ValueError:
        return "gh printed no JSON"
    latest = {}
    for run in sorted(found, key=lambda x: x.get("createdAt", "")):
        latest[run.get("workflowName", "?")] = run
    return list(latest.values())


def full_sha(repo, sha):
    """`gh run list --commit` matches only a full hash; a short one finds nothing."""
    try:
        r = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", sha + "^{commit}"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return sha
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else sha


def verdict(repo, sha, timeout_min=30):
    poll = float(os.environ.get("MAMA_CI_POLL", "15"))
    appear = float(os.environ.get("MAMA_CI_APPEAR", "120"))
    start = time.time()
    short = sha[:9]
    sha = full_sha(repo, sha)
    while True:
        found = runs(repo, sha)
        if isinstance(found, str):
            return 0, f"ci none: {found}"
        waited = time.time() - start
        if not found:
            if waited >= appear:
                return 0, f"ci none: no CI run started for {short} within {round(appear)}s"
        else:
            open_ = [r for r in found if r.get("status") != "completed"]
            if not open_:
                bad = [r for r in found if r.get("conclusion") not in PASS]
                if bad:
                    return 1, f"ci {short}: red — " + "; ".join(
                        f"{r.get('workflowName', '?')} ({r.get('conclusion')}) {r.get('url', '')}".strip() for r in bad)
                return 0, f"ci {short}: green — {len(found)} run{'s' if len(found) != 1 else ''}"
            if waited >= timeout_min * 60:
                return 3, (f"ci {short}: pending — {len(open_)} of {len(found)} runs still running after "
                           f"{round(waited / 60)}m")
        time.sleep(poll)


def main():
    args = sys.argv[1:]
    log, timeout = None, 30.0
    for flag in ("--log", "--timeout"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                sys.exit(__doc__)
            if flag == "--log":
                log = args[i + 1]
            else:
                timeout = float(args[i + 1])
            del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    repo, sha = args
    code, line = verdict(repo, sha, timeout)
    print(line)
    if log:
        import log as logmod  # noqa: E402 — only when writing: records the session that owns the goal
        logmod.write(log, "E", line)
    sys.exit(code)


if __name__ == "__main__":
    main()
