#!/usr/bin/env python3
"""One state call per step: the plan row, the log line, criteria evidence and the overview.

Usage: step.py <plan.md> <Sn> <status> ["text"] [--commit <sha>] [--crit Cn="evidence"]...
  step.py plan.md S3 running
  step.py plan.md S3 done "filter tests pass" --commit abc1234 --crit C2="go test ./... ok"
Does, in one call:
- the plan write, through plan-set.py's own code (its guards, stamps, progress, estimate, budget
  and WARNING lines): status, the text (+ `commit <sha>`) appended to the row's notes, and each
  --crit criterion's evidence — set before the step, so plan-set doesn't warn it is missing;
- one log line via log.py: `E <status> Sn — <text>[ · commit <sha>]`;
- the overview's generated block (overview.py).
Exits non-zero only when the plan write is refused (nothing is logged then).
plan-set.py stays the call for headers, added rows and parking; log.py for decisions and questions.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import log  # noqa: E402
import overview  # noqa: E402


def plan_set():
    spec = importlib.util.spec_from_file_location("plan_set", os.path.join(HERE, "plan-set.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse(argv):
    if len(argv) < 3 or not re.fullmatch(r"S\d+\w*", argv[1]):
        sys.exit(__doc__)
    path, sid, status = argv[:3]
    text, commit, crits, rest = "", "", [], argv[3:]
    i = 0
    while i < len(rest):
        a = rest[i]
        if a in ("--commit", "--crit") and i + 1 < len(rest):
            v = rest[i + 1]
            if a == "--commit":
                commit = v.strip()
            else:
                m = re.fullmatch(r"(C\d+\w*)=(.*)", v, re.S)
                if not m:
                    sys.exit(f"bad --crit {v!r}, want Cn=\"evidence\"")
                crits.append((m.group(1), m.group(2).strip()))
            i += 2
        elif a.startswith("--crit="):
            rest[i:i + 1] = ["--crit", a[len("--crit="):]]
        elif a.startswith("--commit="):
            rest[i:i + 1] = ["--commit", a[len("--commit="):]]
        elif not a.startswith("--") and not text:
            text = " ".join(a.split())
            i += 1
        else:
            sys.exit(__doc__)
    if status.startswith("-") or "=" in status:
        sys.exit(__doc__)
    return path, sid, status, text, commit, crits


def main():
    path, sid, status, text, commit, crits = parse(sys.argv[1:])
    note = " · ".join(x for x in (text, f"commit {commit}" if commit else "") if x)
    ps = plan_set()
    esc = lambda v: ps.parse_updates([f"x={v}"])["x"]  # plan-set's pipe escaping
    orig = ps.set_row

    def set_row(lines, section, row_id, updates):
        # plan-set edits one row per call; the criteria and the notes ride on the step's edit, so
        # they land in the same locked read → write (and before plan-set's evidence check).
        if section == "## Steps" and row_id == sid:
            for cid, ev in crits:
                orig(lines, "## Criteria", cid, {"evidence": esc(ev)})
            if note:
                header, rows = ps.table(lines, section)
                row = next((r for r in rows if ps.cells(lines[r])[0] == sid), None)
                if row is not None and "notes" in header:
                    cur = (ps.cells(lines[row]) + [""] * len(header))[header.index("notes")]
                    updates = dict(updates, notes=f"{cur} · {esc(note)}" if cur else esc(note))
        return orig(lines, section, row_id, updates)

    ps.set_row = set_row
    sys.argv = [os.path.join(HERE, "plan-set.py"), path, sid, f"status={status}"]
    try:
        ps.main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code if isinstance(e.code, str) else "REFUSED: plan write failed")
            sys.exit(1)
    goal = os.path.dirname(os.path.abspath(path))
    logp = os.path.join(goal, "log.md")
    if os.path.exists(logp):
        print(log.write(logp, "E", f"{status} {sid}" + (f" — {note}" if note else "")))
    overview.regenerate(goal)


if __name__ == "__main__":
    main()
