#!/usr/bin/env python3
"""Which session worked on which goal, recorded — not inferred.

The skill's writers (log.py, plan-set.py, new-goal.py) call record(<goal dir>). Claude Code
gives every shell the session's id in CLAUDE_CODE_SESSION_ID, so each write appends
`<iso time> <session id> <goal dir>` to ~/.claude/mama/activity.log (only when the
session's current goal changes). Spend and the hooks read it; goals from before it
existed fall back to reading the transcripts (spend.written_slugs).

Usage: activity.py [<session id>]   # print that session's (or every) goal switches
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402

PATH = os.path.expanduser("~/.claude/mama/activity.log")


def canon(path):
    """One spelling per folder: symlinks resolved (macOS /var is /private/var; git reports the
    resolved path), no trailing slash — so a recorded goal always matches the hook's store."""
    return os.path.realpath(path).rstrip("/")


def entries():
    """[(time, session id, goal dir)] in file order, goal dirs canonical."""
    out = []
    try:
        with open(PATH, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\n").split(" ", 2)
                if len(parts) == 3:
                    try:
                        out.append((datetime.datetime.fromisoformat(parts[0]), parts[1], canon(parts[2])))
                    except ValueError:
                        pass
    except OSError:
        pass
    return out


def record(goal_dir):
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not sid:
        return
    goal_dir = canon(goal_dir)
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "a+", encoding="utf-8") as f, fileio.locked(f):
        mine = [e for e in entries() if e[1] == sid]
        if mine and mine[-1][2] == goal_dir:
            return
        f.write(f"{datetime.datetime.now().isoformat(timespec='seconds')} {sid} {goal_dir}\n")


def timeline(sid):
    """[(time, goal dir)] for one session: its goal switches, oldest first."""
    return [(t, g) for t, s, g in entries() if s == sid]


def goal_at(tl, t):
    cur = None
    for ts, g in tl:
        if ts > t:
            break
        cur = g
    return cur


def sessions_for(goal_dir):
    goal_dir = canon(goal_dir)
    return list(dict.fromkeys(s for _, s, g in entries() if g == goal_dir))


def goals_of(sid):
    """Goal dirs (canonical, any store) this session wrote to, oldest first, by first write.
    Only recorded writes count: hooks write with log.write(record=False) / log.py --no-record,
    so an event line (a compaction, say) never makes a goal the session's."""
    return list(dict.fromkeys(g for _, s, g in entries() if s == sid))


def goals_for(sid):
    """Goal dirs this session wrote to, ordered by last write (most recent last)."""
    order = {}
    for i, (_, s, g) in enumerate(entries()):
        if s == sid:
            order[g] = i
    return sorted(order, key=order.get)


if __name__ == "__main__":
    for t, s, g in entries():
        if len(sys.argv) < 2 or s == sys.argv[1]:
            print(t, s, g)
