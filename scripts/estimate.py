#!/usr/bin/env python3
"""Step estimates: a goal takes about its critical path, not the sum of its steps.

Steps whose deps allow run in parallel, so the time to finish is the longest chain of
dependent steps. Adding every step's estimate over-counted parallel goals 3-4×.

Usage: estimate.py <plan.md>   # prints the critical path, the sum, and what's left
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402,F401  (UTF-8 output)

SKIP = {"obsolete", "parked"}


def expand(deps):
    """'S1-S4, S6a' -> ['S1','S2','S3','S4','S6a']"""
    out = []
    for part in re.split(r"[,\s]+", deps or ""):
        m = re.fullmatch(r"S(\d+)-S?(\d+)", part)
        if m:
            out += [f"S{n}" for n in range(int(m.group(1)), int(m.group(2)) + 1)]
        elif re.fullmatch(r"S\d+\w*", part):
            out.append(part)
    return out


def minutes(est):
    """'15m' -> 15, '1h 20m' -> 80, '' -> 0"""
    return sum(int(n) * (60 if u == "h" else 1) for n, u in re.findall(r"(\d+)\s*([hm])", est or ""))


def critical_path(steps, left=False):
    """steps: [(id, deps, est, status)]. Longest chain of dependent steps, in minutes.
    left=True: done steps count 0 (the time still to go). Obsolete/parked steps are skipped;
    a dependency cycle is cut instead of looping."""
    live = {s[0]: s for s in steps if s[3] not in SKIP}
    memo, active = {}, set()

    def chain(sid):
        if sid in memo:
            return memo[sid]
        if sid in active:
            return 0
        active.add(sid)
        _, deps, est, status = live[sid]
        own = 0 if left and status == "done" else minutes(est)
        memo[sid] = own + max((chain(d) for d in expand(deps) if d in live), default=0)
        active.discard(sid)
        return memo[sid]

    return max((chain(s) for s in live), default=0)


def width(steps, left=False):
    """How many steps can run at once if each starts as soon as its deps finish."""
    live = {s[0]: s for s in steps if s[3] not in SKIP and not (left and s[3] == "done")}
    finish, active = {}, set()

    def end(sid):
        if sid not in finish:
            if sid in active:
                return 0
            active.add(sid)
            start = max((end(d) for d in expand(live[sid][1]) if d in live), default=0)
            finish[sid] = (start, start + max(minutes(live[sid][2]), 1))
            active.discard(sid)
        return finish[sid][1]

    for s in live:
        end(s)
    edges = sorted([(a, 1) for a, _ in finish.values()] + [(b, -1) for _, b in finish.values()],
                   key=lambda e: (e[0], e[1]))
    now = best = 0
    for _, d in edges:
        now += d
        best = max(best, now)
    return best


def total(steps, left=False):
    return sum(minutes(s[2]) for s in steps if s[3] not in SKIP and not (left and s[3] == "done"))


def split_row(line):
    """A markdown table row's cells, raw: `\\|` inside a cell (an escaped pipe) doesn't split it."""
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def table(text, section):
    """The `## <section>` markdown table: (header cells, rows). Rows with an empty first cell are
    skipped; short rows are padded so every row indexes like the header."""
    m = re.search(rf"^## {section}\n(.*?)(?=^## |\Z)", text or "", re.M | re.S)
    rows = [[c.replace("\\|", "|") for c in split_row(l)]
            for l in (m.group(1).splitlines() if m else []) if l.lstrip().startswith("|")]
    if len(rows) < 2:
        return [], []
    w = len(rows[0])
    return rows[0], [r + [""] * (w - len(r)) for r in rows[2:] if r and r[0]]


def steps_of(plan_text):
    """[(id, deps, est, status)] for every step row."""
    hdr, rows = table(plan_text, "Steps")
    i = {k: n for n, k in enumerate(hdr)}
    if not {"deps", "est", "status"} <= i.keys():
        return []
    return [(r[0], r[i["deps"]], r[i["est"]], r[i["status"]]) for r in rows]


def summary(plan_text):
    s = steps_of(plan_text)
    if not any(minutes(x[2]) for x in s):
        return ""
    return (f"estimate: critical path {critical_path(s)}m (sum {total(s)}m, up to {width(s)} at once) · "
            f"left {critical_path(s, left=True)}m — runs typically take ~⅔ of the critical path (rules/planning.md)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(summary(open(sys.argv[1], encoding="utf-8").read()) or "no step estimates")
