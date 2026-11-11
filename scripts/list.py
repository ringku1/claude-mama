#!/usr/bin/env python3
"""List the goals in a store: one line per goal folder, open goals first, newest first.

Usage:
  list.py <store>

Each line: <slug>  <status>  <progress>  <worktree>, read from <store>/<slug>/plan.md's header.
A folder without plan.md is listed as "no plan.md". Open = any status but done or aborted.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileio  # noqa: E402,F401  (UTF-8 output on Windows consoles)

CLOSED = {"done", "aborted"}


def header(text):
    vals = {}
    for line in text.split("\n"):
        if line.startswith("## "):
            break
        for part in line.split(" | "):
            m = re.match(r"\s*([a-z][a-z ]*):\s*(.*?)\s*$", part)
            if m and m.group(1) not in vals:
                vals[m.group(1)] = m.group(2)
    return vals


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    store = sys.argv[1]
    if not os.path.isdir(store):
        sys.exit(f"no store at {store}")
    rows = []
    for slug in os.listdir(store):
        d = os.path.join(store, slug)
        if not os.path.isdir(d) or slug.startswith("."):
            continue
        plan = os.path.join(d, "plan.md")
        if not os.path.isfile(plan):
            rows.append((True, -os.path.getmtime(d), slug, "no plan.md", "—", "—"))
            continue
        with open(plan, encoding="utf-8") as f:
            h = header(f.read())
        status = h.get("status") or "—"
        progress = (h.get("progress") or "—").strip()
        worktree = h.get("worktree") or "—"
        rows.append((status not in CLOSED, -os.path.getmtime(plan), slug, status, progress, worktree))
    if not rows:
        print("no goals")
        return
    rows.sort(key=lambda r: (not r[0], r[1], r[2]))
    w = [max(len(r[i]) for r in rows) for i in (2, 3, 4)]
    for r in rows:
        print(f"{r[2]:<{w[0]}}  {r[3]:<{w[1]}}  {r[4]:<{w[2]}}  {r[5]}".rstrip())


if __name__ == "__main__":
    main()
