#!/usr/bin/env python3
"""Keep overview.md's **Status:** line in step with plan.md, and mark milestones.

The Status line is the one part of the overview that follows from state, so plan-set.py
rewrites it after every write: `**Status:** <Word> · <n> of <m> parts done[ · detail]`
(the detail is kept while the status word stays the same). The overview's mtime is kept, so
the prose still counts as unrefreshed.

A milestone (a step done/blocked/dropped, the goal's status or PR changed, scope added)
touches `<goal>/.milestone`; the Stop hook asks for the prose (Where we are, Timeline) to be
refreshed only when the overview is older than the last milestone — not after every plan write.

Usage: overview.py <goal dir>   # sync the Status line now
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402

WORDS = {"planning": "Planning", "approved": "Approved", "running": "Working", "waiting": "Waiting for you",
         "paused": "Paused", "blocked": "Blocked", "done": "Done", "aborted": "Stopped"}
STATUS_RE = re.compile(r"^\*\*Status:\*\*.*$", re.M)
MARK = ".milestone"


def status_line(plan_text):
    head = plan_text.split("\n## ")[0]
    st = re.search(r"status: (\w+)", head)
    pr = re.search(r"progress: (\d+)/(\d+)", head)
    word = WORDS.get(st.group(1), st.group(1).capitalize()) if st else "Planning"
    if pr and int(pr.group(2)):
        return f"**Status:** {word} · {pr.group(1)} of {pr.group(2)} parts done"
    return f"**Status:** {word}"


def merged(old, new):
    """Keep the hand-written detail after the progress while the status word is unchanged."""
    m = re.match(r"\*\*Status:\*\* ([^·]+?) · [^·]+? · (.+)$", old)
    if m and new.startswith(f"**Status:** {m.group(1)} ·"):
        return f"{new} · {m.group(2)}"
    return new


def sync(goal):
    ov = os.path.join(goal, "overview.md")
    try:
        text = open(ov, encoding="utf-8").read()
        plan = open(os.path.join(goal, "plan.md"), encoding="utf-8").read()
    except OSError:
        return
    m = STATUS_RE.search(text)
    if not m:
        return  # close-check reports a missing Status line
    line = merged(m.group(0), status_line(plan))
    if line == m.group(0):
        return
    st = os.stat(ov)
    fileio.write_atomic(ov, text[:m.start()] + line + text[m.end():])
    os.utime(ov, (st.st_atime, st.st_mtime))


def milestone(goal):
    p = os.path.join(goal, MARK)
    with open(p, "a"):
        pass
    os.utime(p)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sync(os.path.abspath(sys.argv[1]))
